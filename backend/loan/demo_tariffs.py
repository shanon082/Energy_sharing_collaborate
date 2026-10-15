"""Strict demo adapter for utils.billing; no alternate pricing calculation.

Owner-level bands match existing billing, but only settled UGX_DEMO purchases
enter this ledger. Frozen inputs are sufficient to reproduce accepted terms.
"""
from dataclasses import asdict
from decimal import Decimal
from hashlib import sha256
import json
from types import SimpleNamespace

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from loan.models import ElectricityTariff
from meter.models import EnergyAllocation
from utils import billing

VERSION = "DEMO-DOMESTIC-BILLING-v1"


def unavailable(message="Tariff unavailable"):
    raise ValidationError({"code": "TARIFF_UNAVAILABLE", "message": message})


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def pricing_inputs(owner):
    today = timezone.localdate()
    # Unlike the legacy fallback, never select expired or future schedules.
    rows = list(ElectricityTariff.objects.filter(is_active=True, tariff_type="DOMESTIC")
        .filter(Q(effective_from__lte=today) | Q(effective_from__isnull=True, effective_date__date__lte=today))
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today)).prefetch_related("blocks"))
    if len(rows) != 1:
        unavailable("Tariff unavailable: exactly one effective active domestic schedule is required.")
    tariff = rows[0]
    blocks = list(tariff.blocks.order_by("block_order", "pk"))
    if not blocks or not tariff.service_charge.is_finite() or tariff.service_charge < 0:
        unavailable()
    previous_max = 0
    seen_orders = set()
    for index, block in enumerate(blocks):
        lower = max(0, block.min_units - 1)
        if (block.block_order in seen_orders or lower != previous_max or not block.rate_per_unit.is_finite() or block.rate_per_unit <= 0
                or (block.is_lifeline_block and block.non_lifeline_rate is not None and (not block.non_lifeline_rate.is_finite() or block.non_lifeline_rate <= 0))
                or (block.max_units is not None and block.max_units <= lower)
                or (block.max_units is None and index != len(blocks) - 1)):
            unavailable("Tariff unavailable: inconsistent purchase bands.")
        previous_max = block.max_units
        seen_orders.add(block.block_order)
    if previous_max is not None:
        unavailable("Tariff unavailable: a final open-ended purchase band is required.")
    purchased = EnergyAllocation.objects.filter(owner=owner, accounting_environment="UGX_DEMO",
        purchase_intent__owner=owner, purchase_intent__provider="LOCAL_DEMO", purchase_intent__currency="UGX",
        purchase_intent__purpose="PURCHASE", purchase_intent__status="SETTLED",
        created_at__year=today.year, created_at__month=today.month).aggregate(total=Sum("amount_kwh"))["total"] or Decimal(0)
    if not purchased.is_finite() or purchased < 0:
        unavailable("Tariff unavailable: purchase totals require reconciliation.")
    try:
        eligible = owner.profile.lifeline_eligible
    except (AttributeError, ObjectDoesNotExist):
        unavailable("Tariff unavailable: lifeline eligibility configuration is missing.")
    if not eligible and any(b.is_lifeline_block and b.non_lifeline_rate is None for b in blocks):
        unavailable("Tariff unavailable: non-lifeline rate missing.")
    if not isinstance(eligible, bool):
        unavailable("Tariff unavailable: lifeline eligibility configuration is missing.")
    return {"version": VERSION, "currency": "UGX", "environment": "UGX_DEMO", "scope": "OWNER_MONTH",
        "month": today.strftime("%Y-%m"), "tariff": {"id": tariff.pk, "code": tariff.tariff_code,
            "name": tariff.tariff_name, "type": tariff.tariff_type, "service_charge": str(tariff.service_charge),
            "effective_from": tariff.effective_from.isoformat() if tariff.effective_from else None,
            "effective_to": tariff.effective_to.isoformat() if tariff.effective_to else None,
            "legacy_effective_date": tariff.effective_date.isoformat(),
            "blocks": [{"id": b.pk, "block_order": b.block_order, "min_units": b.min_units, "max_units": b.max_units,
                "rate_per_unit": str(b.rate_per_unit), "is_lifeline_block": b.is_lifeline_block,
                "non_lifeline_rate": str(b.non_lifeline_rate) if b.non_lifeline_rate is not None else None} for b in blocks]},
        "monthly_purchased_kwh": str(purchased), "lifeline_eligible": eligible,
        "lifeline_source": "Existing Profile.lifeline_eligible pilot configuration; not utility verification",
        "vat_rate": str(billing.VAT_RATE), "rounding": "Energy floored to 0.01 kWh = 10 Wh; billing charges half-even to 0.01 UGX; exact residual retained"}


class FrozenBlocks(list):
    def exists(self):
        return bool(self)

    def order_by(self, *fields):
        return self


def price_from_snapshot(amount, inputs):
    if inputs.get("version") != VERSION or inputs.get("currency") != "UGX" or inputs.get("environment") != "UGX_DEMO":
        unavailable()
    tariff = inputs["tariff"]
    frozen = SimpleNamespace(service_charge=Decimal(tariff["service_charge"]), blocks=FrozenBlocks(
        SimpleNamespace(**block) for block in tariff["blocks"]))
    context = billing.PurchaseBillingContext(Decimal(inputs["monthly_purchased_kwh"]),
        inputs["lifeline_eligible"], Decimal(inputs["vat_rate"]))
    try:
        units, bill = billing.calculate_units_from_payment(amount, None, tariff=frozen,
            apply_deductions=False, context=context, strict=True)
    except billing.TariffConfigurationError:
        unavailable()
    if units <= 0:
        raise ValidationError({"code": "AMOUNT_BELOW_TARIFF_MINIMUM",
            "message": f"This amount yields less than 10 Wh. The configured tariff requires at least UGX {bill.total} before whole-UGX rounding."})
    return units, bill.total, amount - bill.total, {k: format(v.quantize(Decimal("0.01")), "f") if isinstance(v, Decimal) else v for k, v in asdict(bill).items()}


def quote_price(owner, amount):
    inputs = pricing_inputs(owner)
    units, billed, residual, breakdown = price_from_snapshot(amount, inputs)
    return units, billed, residual, {"inputs": inputs, "inputs_hash": fingerprint(inputs), "breakdown": breakdown}


def require_current_quote(owner, quote):
    pricing = quote.terms.get("pricing")
    if not pricing or pricing.get("inputs_hash") != fingerprint(pricing_inputs(owner)):
        raise ValidationError({"code": "QUOTE_STALE", "message": "Tariff, monthly purchases or pricing settings changed. Review a new quote."})


def validate_frozen_pricing(amount, terms):
    pricing = terms["pricing"]
    inputs = pricing["inputs"]
    units, billed, residual, breakdown = price_from_snapshot(amount, inputs)
    return (pricing.get("inputs_hash") == fingerprint(inputs) and pricing.get("breakdown") == breakdown
        and (units, billed, residual) == tuple(Decimal(terms[k]) for k in ("energy_kwh", "billed", "residual")))
