from tessera_sdk.clients.sendly import SendlyClient
from tessera_sdk.config import get_settings as get_sdk_settings
from tessera_sdk.infra.auth_token_provider import AuthTokenProvider


def build_sendly_client() -> SendlyClient:
    """
    Build a SendlyClient authenticated for service-to-service calls.

    Shared by SendCampaignCommand and the campaign status poller so the
    base_url/token wiring lives in exactly one place. base_url comes from
    tessera_sdk's own settings (already configured as `sendly_api_url`,
    unrelated to this app's app/config.py Settings); the token is a
    short-lived M2M/OAuth token from AuthTokenProvider, resolved fresh on
    each call rather than cached, since SendlyClient itself does no
    refreshing.
    """
    return SendlyClient(
        base_url=get_sdk_settings().sendly_api_url,
        api_token=AuthTokenProvider().get_token(),
    )
