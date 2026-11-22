"""One existing reference, status-only: cannot initiate, settle or mutate a row."""
import json
import uuid
from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import PermissionDenied
from loan.sandbox_service import require_sandbox
from transactions.models import PaymentIntent
from transactions.checkouts import checkout_info, classification
from transactions.payment_settlement import PaymentSettlementError
from transactions.sandbox_payments import validate_sandbox_evidence, SandboxEvidenceError
from mtn_momo.sandbox import MTNSandbox, SandboxProviderError
from mtn_momo.diagnostics import test_scenario


class Command(BaseCommand):
    help = 'Inspect one existing MTN sandbox reference. --lookup performs authenticated GET only; never submits or settles.'

    def add_arguments(self, parser):
        parser.add_argument('--reference', required=True, type=uuid.UUID)
        parser.add_argument('--lookup', action='store_true')

    def handle(self, *args, **options):
        require_sandbox()
        row = PaymentIntent.objects.filter(provider='MTN_SANDBOX', currency='EUR',
                                           provider_reference=options['reference']).first()
        if row is None:
            raise CommandError('Existing MTN sandbox reference not found; nothing submitted.')
        checkout = checkout_info(row)
        result = {'intent_id': row.pk, 'reference': str(row.provider_reference), 'purpose': row.purpose,
                  'stored_status': row.status, 'submission_state': row.submission_state,
                  'classification': classification(row), 'attempts': row.reconcile_attempts,
                  'last_error': row.reconciliation_error, 'next_check_at': row.reconcile_after.isoformat(),
                  'checkout_state': checkout['state'], 'operation_reference': checkout['operation_reference'],
                  'fulfilled_reference': checkout['fulfilled_reference'],
                  'test_scenario': test_scenario((row.sandbox_context or {}).get('msisdn')),
                  'lookup_performed': False, 'writes': False, 'submission_performed': False}
        if options['lookup']:
            adapter = None
            try:
                adapter = MTNSandbox(recovery=True)
                evidence = adapter.status(row)
                result.update(lookup_performed=True, **adapter.last_diagnostic)
                # Never expose amounts, payer, external ID, transaction ID or bodies.
                if evidence['status'] in {'SUCCESS', 'FAILED'}:
                    validate_sandbox_evidence(row, evidence)
                    result['validation'] = 'MATCHED; NOT SETTLED BY THIS READ_ONLY_COMMAND'
                else:
                    result['validation'] = 'NON_TERMINAL; NO_FINANCIAL_EFFECT'
            except SandboxEvidenceError as exc:
                result['validation'] = exc.code
            except SandboxProviderError as exc:
                result.update(lookup_performed=True, **adapter.last_diagnostic)
                result['validation'] = exc.code
            except (PaymentSettlementError, PermissionDenied):
                result['validation'] = 'CONFIGURATION_OR_SOURCE_UNAVAILABLE'
        self.stdout.write(json.dumps(result, sort_keys=True))
