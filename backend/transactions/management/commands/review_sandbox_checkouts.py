"""Preview-first, no provider traffic and no inferred financial outcomes."""
from django.core.management.base import BaseCommand, CommandError
from transactions.models import PaymentIntent
from transactions.checkouts import classification, checkout_info, expire_checkout, TEST_PROVIDERS
from loan.sandbox_service import require_sandbox


class Command(BaseCommand):
    help = 'Read-only sandbox checkout report. --expire persists local timeout only; never calls a provider or settles.'

    def add_arguments(self, parser):
        parser.add_argument('--expire', action='store_true')
        parser.add_argument('--limit', type=int, default=20)
        parser.add_argument('--reference')
        parser.add_argument('--request-id')

    def handle(self, *args, **options):
        require_sandbox()
        if not 1 <= options['limit'] <= 100:
            raise CommandError('Use limit 1–100.')
        rows = PaymentIntent.objects.filter(provider__in=TEST_PROVIDERS).order_by('initiated_at', 'pk')
        if options['reference'] and options['request_id']:
            raise CommandError('Select one reference or request ID.')
        selected = options['reference'] or options['request_id']
        if selected:
            import uuid
            try:
                reference = uuid.UUID(selected)
            except ValueError:
                raise CommandError('Use a valid non-secret payment reference.') from None
            rows = rows.filter(**{'provider_reference' if options['reference'] else 'client_request_id': reference})
        else:
            rows = rows.filter(status='PENDING')
        self.stdout.write('LOCAL_EXPIRY_ONLY' if options['expire'] else 'DRY_RUN; no writes or provider calls')
        for row in rows[:options['limit']]:
            if options['expire']:
                expire_checkout(row.pk)
                row = PaymentIntent.objects.get(pk=row.pk)
            info = checkout_info(row)
            self.stdout.write(f'intent_id={row.pk} reference={row.provider_reference} request_id={row.client_request_id} provider={row.provider} purpose={row.purpose} '
                f'provider_status={row.status} classification={classification(row)} initiated_at={row.initiated_at.isoformat()} '
                f'checkout={info["state"]} operation={info["operation_reference"]} fulfills={info["fulfilled_reference"] or "none"}; '
                'no personal records or provider evidence bodies displayed')
