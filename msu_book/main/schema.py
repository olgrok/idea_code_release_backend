from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.plumbing import build_bearer_security_scheme_object


class AuthScheme(OpenApiAuthenticationExtension):
    target_class = "my_auth.authentication.ThirdPartyAuthentication"
    name = "ThirdPartyAuthentication"

    def get_security_definition(self, auto_schema):
        return build_bearer_security_scheme_object(
            header_name='Authorization',
            token_prefix=''
        )
