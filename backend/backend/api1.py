from django.urls import include, path

urlpatterns = [
    path(
        "auth/",
        include(("accounts.api.urls", "auth"), namespace="auth"),
    ),
    path(
        "meter/",
        include(
            ("meter.api.urls", "meter"), namespace="meter"
        ),
    ),
    path(
        "transactions/",
        include(
            ("transactions.api.urls", "transactions"), namespace="transactions"
        ),
    ),
    path(
        "webhooks/",
        include(
            ("webhooks.api.urls", "webhooks"), namespace="webhooks"
        ),
    ),
    path(
        "loans/",
        include(
            ("loan.api.urls", "loan"), namespace="loan"
        ),
    ),
    path(
        "wallet/",
        include(
            ("wallet.urls", "wallet"), namespace="wallet" 
        ),
    ),
    path(
        "share/",
        include(
            ("share.urls", "share"), namespace="share"
        ),
    ),
    path(
        "ussd/",
        include(
            ("ussd.urls", "ussd"), namespace="ussd"
        ),
    ),
]
