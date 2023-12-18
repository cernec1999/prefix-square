from decimal import Decimal
from typing import Any, Dict, Union
from django.http import HttpRequest
from pretix.base.models import Order
from pretix.base.payment import BasePaymentProvider, PaymentException, WalletQueries
from django.template.loader import get_template
from django.conf import settings
from django.contrib import messages
from django.utils.translation import gettext, gettext_lazy as _, pgettext
from collections import OrderedDict
from django.urls import reverse
from pretix.base.settings import SettingsSandbox
from django import forms
from pretix.base.models import (
    Event, InvoiceAddress, Order, OrderPayment, OrderRefund, Quota,
)
import logging
logger = logging.getLogger('pretix.plugins.pretix_square')
from pretix.base.services.mail import SendMailException
from square.client import Client

# TODO: Replace with production token
client = Client(access_token='FIXME', environment='production')

class SquareCC(BasePaymentProvider):
    identifier = 'square'
    verbose_name = 'Square'
    public_name = 'Credit card'
    method = 'card'
    payment_form_fields = OrderedDict([])

    def __init__(self, event):
        super().__init__(event)
        self.settings = SettingsSandbox('payment', 'square', event)

    # template = get_template('pretix_square/card.html')
    def payment_form_render(self, request: HttpRequest, total: Decimal, order: Order = None) -> str:
        template = get_template('pretix_square/checkout_payment_form_card.html')
        ctx = {
            'request': request,
            'event': self.event,
            'total': self._decimal_to_int(total),
            'settings': self.settings,
            'form': self.payment_form(request)
        }
        return template.render(ctx)
    
    @property
    def payment_form_fields(self):
        # Just get the customer first name, last name, and billing address
        return OrderedDict(
            [
                ('first_name', forms.CharField(label=_('First name'), max_length=255, required=True)),
                ('last_name', forms.CharField(label=_('Last name'), max_length=255, required=True)),
                ('address_line_1', forms.CharField(label=_('Address line 1'), max_length=255, required=True)),
                ('address_line_2', forms.CharField(label=_('Address line 2'), max_length=255, required=False)),
                ('city', forms.CharField(label=_('City'), max_length=255, required=True)),
                ('state', forms.CharField(label=_('State'), max_length=255, required=True)),
                ('country_code', forms.CharField(label=_('Country code'), max_length=2, required=True)),
            ]
        )
    
    def checkout_prepare(self, request: HttpRequest, cart: Dict[str, Any]) -> bool | str:
        request.session['payment_square_card_brand'] = request.POST.get('square_card_brand', '')
        request.session['payment_square_card_last4'] = request.POST.get('square_card_last4', '')
        request.session['payment_square_card_location_id'] = request.POST.get('square_card_location_id', '')
        request.session['payment_square_card_source_id'] = request.POST.get('square_card_source_id', '')
        request.session['payment_square_card_verification'] = request.POST.get('square_card_verification', '')
        request.session['payment_square_card_idempotency_token'] = request.POST.get('square_card_idempotency_token', '')
        square_card_source_id = request.POST.get('square_card_source_id', '')

        if square_card_source_id == '':
            messages.warning(request, _('You may need to enable JavaScript for Square payments.'))
            return False
        return True
    
    def payment_prepare(self, request: HttpRequest, payment: OrderPayment) -> bool | str:
        request.session['payment_square_card_brand'] = request.POST.get('square_card_brand', '')
        request.session['payment_square_card_last4'] = request.POST.get('square_card_last4', '')
        request.session['payment_square_card_location_id'] = request.POST.get('square_card_location_id', '')
        request.session['payment_square_card_source_id'] = request.POST.get('square_card_source_id', '')
        request.session['payment_square_card_verification'] = request.POST.get('square_card_verification', '')
        request.session['payment_square_card_idempotency_token'] = request.POST.get('square_card_idempotency_token', '')
        square_card_source_id = request.POST.get('square_card_source_id', '')

        if square_card_source_id == '':
            messages.warning(request, _('You may need to enable JavaScript for Square payments.'))
            return False
        return True
    
    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        if not self.payment_is_valid_session(request):
            raise PaymentException(_('We were not able to process your credit card information. Please try again.'))

        # Create a square payment
        amount = self._decimal_to_int(payment.amount)
        currency = self.event.currency

        square_payment={
            'idempotency_key':request.session['payment_square_card_idempotency_token'],
            'source_id':request.session['payment_square_card_source_id'],
            'verification_token':request.session['payment_square_card_verification'],
            'amount_money':{
                'amount': amount,
                'currency': currency
            }
        }
        
        intent = client.payments.create_payment(square_payment)

        # If intent errors attribute is not an empty list, raise an exception
        if intent.errors and len(intent.errors) > 0:
            # Join all error messages into one string
            error_message = ''
            for error in intent.errors:
                error_message += error['detail'] + ', '
            
            # Remove the last comma and space
            error_message = error_message[:-2]
            
            logger.info('Square card error: %s' % str(intent.errors))
            payment.fail(info={
                'error': True,
                'message': error_message,
            })
            raise PaymentException(_('We were not able to process your credit card information. ' + error_message))
        
        # if intent.body.payment does not exist, or intent.payment.status is not equal to 'COMPLETED'
        if not intent.body['payment'] or intent.body['payment']['status'] != 'COMPLETED':
            logger.info('Square card error (no payment field): %s' % intent.text)
            payment.fail(info={
                'error': True,
                'message': 'Payment failed',
            })
            raise PaymentException(_('We were not able to process your credit card information.'))

        try:
            payment.info = intent.text
            payment.confirm()
        except Quota.QuotaExceededException as e:
            raise PaymentException(str(e))

        except SendMailException:
            raise PaymentException(_('There was an error sending the confirmation mail.'))
    
    def payment_is_valid_session(self, request):
        # Check if we have last4 and brand in the session
        return request.session.get('payment_square_card_brand', False) and request.session.get('payment_square_card_last4', False)
    
    def checkout_confirm_render(self, request) -> str:
        template = get_template('pretix_square/checkout_payment_confirm.html')
        ctx = {'request': request, 'event': self.event, 'settings': self.settings, 'provider': self}
        return template.render(ctx)
    
    def _decimal_to_int(self, amount):
        places = settings.CURRENCY_PLACES.get(self.event.currency, 2)
        return int(amount * 10 ** places)