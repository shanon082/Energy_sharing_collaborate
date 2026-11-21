"""Read-only purchase/token chain report. Never return token digits or keys."""
from decimal import Decimal
from django.core.exceptions import ImproperlyConfigured
from meter.models import Meter, PrototypeDevice, EnergyKeypadToken
from meter.energy_tokens import cipher, digest_token
from meter.prototype_device import lab_source, enabled, DOMAIN_PROTOCOLS, active_binding
from meter.bench_device import payload_digest
from transactions.models import PaymentIntent


def audit_credit(owner_id, meter_id, reference=None, limit=5):
    meter = Meter.objects.get(pk=meter_id, user_id=owner_id)
    devices = list(PrototypeDevice.objects.filter(owner_id=owner_id, meter=meter))
    payments = PaymentIntent.objects.filter(owner_id=owner_id, meter=meter, purpose='PURCHASE').order_by('-initiated_at')
    if reference:
        payments = payments.filter(provider_reference=reference)
    result = {'read_only': True, 'provider_requeried': False, 'lab_enabled': enabled(), 'owner_id': owner_id,
              'meter_id': meter_id, 'devices': [{'id': str(d.pk), 'environment': d.environment,
              'protocol': DOMAIN_PROTOCOLS.get(d.environment), 'active': d.active and not bool(d.revoked_at),
              'output_enabled': d.output_enabled, 'application_counter': d.application_counter,
              'pending_commands': list(d.commands.filter(receipt_id__isnull=True).values_list('delivery_id', flat=True))} for d in devices], 'purchases': []}
    for device, summary in zip(devices, result['devices']):
        try:
            active_binding(device)
            summary['current_binding_valid'] = True
        except Exception:
            summary['current_binding_valid'] = False
    for intent in payments[:limit]:
        allocation = getattr(intent, 'energy_allocation', None)
        receipt = getattr(intent, 'sandbox_settlement', None)
        token = getattr(allocation, 'keypad_token', None) if allocation else None
        row = {'purchase_reference': str(intent.provider_reference), 'status': intent.status, 'provider': intent.provider,
               'currency': intent.currency, 'provider_transaction_present': bool(intent.provider_transaction_id),
               'settlement_present': receipt is not None, 'allocation_id': allocation.pk if allocation else None,
               'allocation_environment': allocation.accounting_environment if allocation else None,
               'token_id': str(token.pk) if token else None, 'checks': []}
        checks = row['checks']
        if intent.status != 'SETTLED' or not receipt or not intent.provider_transaction_id:
            checks.append('STORED_SETTLEMENT_INCOMPLETE')
        if receipt and (receipt.currency != intent.currency or receipt.received != intent.amount or receipt.billed + receipt.residual != receipt.received):
            checks.append('SETTLEMENT_AMOUNT_OR_CURRENCY_MISMATCH')
        if not token:
            checks.append('TOKEN_NOT_ISSUED')
        else:
            row.update(token_state=token.state, token_environment=token.environment, delivery_id=token.delivery_id)
            try:
                plain = cipher().decrypt(token.ciphertext.encode()).decode('ascii')
                if len(plain) != 15 or not plain.isascii() or not plain.isdigit() or digest_token(plain) != token.lookup_digest:
                    checks.append('TOKEN_LOOKUP_INTEGRITY_FAILURE')
            except ImproperlyConfigured:
                checks.append('TOKEN_KEY_CONFIGURATION_UNAVAILABLE')
            except Exception:
                checks.append('TOKEN_ENCRYPTION_INTEGRITY_FAILURE')
            if (token.owner_id != owner_id or token.meter_id != meter_id or token.meter_number != meter.meter_no
                    or token.environment != allocation.accounting_environment):
                checks.append('TOKEN_BINDING_MISMATCH')
            if not any(d.environment == token.environment for d in devices):
                checks.append('DEVICE_TOKEN_ENVIRONMENT_MISMATCH')
            if not lab_source(allocation, allocation.accounting_environment):
                checks.append('TOKEN_SOURCE_UNVERIFIED')
            try:
                if Decimal(intent.sandbox_context['terms']['energy_kwh']) * 1000 != token.amount_wh:
                    checks.append('ACCEPTED_ENERGY_MISMATCH')
            except (KeyError, TypeError, ArithmeticError):
                checks.append('ACCEPTED_TERMS_UNAVAILABLE')
            if token.delivery_id:
                delivery = token.delivery
                row['delivery_state'] = delivery.status
                command = getattr(delivery, 'prototype_command', None)
                row['ack_present'] = bool(command and command.receipt_id)
                frozen = delivery.command_payload or {}
                if frozen.get('payload_digest') != payload_digest({k: v for k, v in frozen.items() if k != 'payload_digest'}):
                    checks.append('COMMAND_DIGEST_MISMATCH')
        if not checks:
            checks.append('STORED_CHAIN_CONSISTENT_PROVIDER_NOT_REQUERIED')
        result['purchases'].append(row)
    return result
