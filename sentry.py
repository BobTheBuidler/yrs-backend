import os

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration


def setup_sentry():
    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN",None),
        integrations=[FlaskIntegration()],

        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=1.0
    )
