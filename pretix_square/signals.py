from django.dispatch import receiver
from django.http import HttpRequest, HttpResponse
from django.template.loader import get_template
from django.urls import resolve
from pretix.base.middleware import _merge_csp, _parse_csp, _render_csp
from pretix.base.signals import register_payment_providers
from pretix.presale.signals import html_head, process_response


@receiver(register_payment_providers, dispatch_uid="pretix_square")
def register_payment_provider(sender, **kwargs):
    from .payment import SquareCC

    return SquareCC


@receiver(html_head, dispatch_uid="payment_square_html_head")
def html_head_presale(sender, request=None, **kwargs):
    url = resolve(request.path_info)
    # print(url)
    if (url.url_name == "event.checkout" and url.kwargs["step"] == "payment") or (
        url.url_name == "event.order.pay.change"
    ):
        template = get_template("pretix_square/presale_head.html")
        ctx = {"event": sender}
        return template.render(ctx)
    else:
        return ""


@receiver(signal=process_response, dispatch_uid="square_middleware_resp")
def signal_process_response(
    sender, request: HttpRequest, response: HttpResponse, **kwargs
):
    url = resolve(request.path_info)

    if (
        url.url_name == "event.order.pay.change"
        or url.url_name == "event.order.pay"
        or (url.url_name == "event.checkout" and url.kwargs["step"] == "payment")
        or (url.namespace == "plugins:stripe" and url.url_name in ["sca", "sca.return"])
    ):
        if "Content-Security-Policy" in response:
            h = _parse_csp(response["Content-Security-Policy"])
        else:
            h = {}

        # Unfortunately, the official Square documentation is incomplete. We should verify
        # that these are the only CSPs required for Square Checkout.
        csps = {
            "connect-src": [
                "https://connect.squareupsandbox.com/",
                "https://connect.squareup.com/",
                "https://pci-connect.squareupsandbox.com/",
                "https://pci-connect.squareup.com/",
                "https://o160250.ingest.sentry.io/",
            ],
            "frame-src": [
                "https://*.squarecdn.com/",
                "https://connect.squareupsandbox.com/",
                "https://connect.squareup.com/",
                "https://api.squareupsandbox.com/",
                "https://api.squareup.com/",
                "https://geoissuer.cardinalcommerce.com/",
            ],
            "script-src": [
                "https://*.squarecdn.com/",
                "https://js.squareupsandbox.com/",
                "https://js.squareup.com/",
            ],
            "style-src": ["'unsafe-inline'", "https://*.squarecdn.com/"],
            "font-src": [
                "https://*.squarecdn.com/",
                "https://d1g145x70srn7h.cloudfront.net/",
            ],
        }

        _merge_csp(h, csps)

        # Old code
        # if h:
        #     response["Content-Security-Policy"] = _render_csp(h)

        # TODO: For now, due to SCA, remove the CSP header.
        if "Content-Security-Policy" in response:
            del response["Content-Security-Policy"]

    return response
