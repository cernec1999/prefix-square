from django.dispatch import receiver
from django.urls import resolve, reverse
from django.template.loader import get_template
from pretix.base.signals import register_payment_providers, logentry_display
from pretix.presale.signals import html_head, process_response
from pretix.base.middleware import _merge_csp, _parse_csp, _render_csp
from django.http import HttpRequest, HttpResponse

@receiver(register_payment_providers, dispatch_uid="pretix_square")
def register_payment_provider(sender, **kwargs):
    from .payment import SquareCC
    return SquareCC

@receiver(html_head, dispatch_uid="payment_square_html_head")
def html_head_presale(sender, request=None, **kwargs):
    url = resolve(request.path_info)
    # print(url)
    if (url.url_name == "event.checkout" and url.kwargs['step'] == "payment") or (url.url_name == "event.order.pay.change"):
        template = get_template('pretix_square/presale_head.html')
        ctx = {
            'event': sender
        }
        return template.render(ctx)
    else:
        return ""
    

@receiver(signal=process_response, dispatch_uid="square_middleware_resp")
def signal_process_response(sender, request: HttpRequest, response: HttpResponse, **kwargs):
    url = resolve(request.path_info)

    if url.url_name == "event.order.pay.change" or url.url_name == "event.order.pay" or (url.url_name == "event.checkout" and url.kwargs['step'] == "payment") or (url.namespace == "plugins:stripe" and url.url_name in ["sca", "sca.return"]):
        if 'Content-Security-Policy' in response:
            h = _parse_csp(response['Content-Security-Policy'])
        else:
            h = {}

        csps = {
            'connect-src': ['https://connect.squareupsandbox.com/', 'https://pci-connect.squareupsandbox.com/', 'https://o160250.ingest.sentry.io'],
            'frame-src': ['https://sandbox.web.squarecdn.com', 'https://connect.squareupsandbox.com/', 'https://api.squareupsandbox.com/'],
            'script-src': ['https://sandbox.web.squarecdn.com'],
            'style-src': ['\'unsafe-inline\'', 'https://sandbox.web.squarecdn.com'],
            'font-src': ['https://square-fonts-production-f.squarecdn.com/', 'https://d1g145x70srn7h.cloudfront.net/'],
        }

        _merge_csp(h, csps)

        if h:
            response['Content-Security-Policy'] = _render_csp(h)

    return response