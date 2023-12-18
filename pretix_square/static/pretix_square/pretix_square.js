/* TODO: Replace with production token
 *
 * In the future, we will allow the developer to specify
 * these values in the plugin configuration.
 */
const appId = 'FIXME';
const locationId = 'FIXME';

function loadSquareSdk() {
    return new Promise((resolve, reject) => {
        $.getScript('https://sandbox.web.squarecdn.com/v1/square.js')
            .done(function (script, textStatus) {
                resolve();
            })
            .fail(function (jqxhr, settings, exception) {
                console.error("Error loading Square SDK");
                reject(exception);
            });
    });
}

// Usage
async function init() {
    try {
        await loadSquareSdk();
        if (!window.Square) {
            $(".square-errors").stop().hide().removeClass("sr-only");
            $(".square-errors").html("<div class='alert alert-danger'>Square.js failed to load properly</div>");
            $(".square-errors").slideDown();
        }

        let payments;
        try {
            payments = window.Square.payments(appId, locationId);
        } catch (e) {
            console.error('Initializing Payments failed', e);
            $(".square-errors").stop().hide().removeClass("sr-only");
            $(".square-errors").html("<div class='alert alert-danger'>" + e.message + "</div>");
            $(".square-errors").slideDown();
            return;
        }

        let card;
        try {
            card = await initializeCard(payments);
        } catch (e) {
            console.error('Initializing Card failed', e);
            return;
        }

        async function handlePaymentMethodSubmission(card) {
            try {
                const token = await tokenize(card);
                const verificationToken = await verifyBuyer(payments, token);
                console.log('Verification Token', verificationToken)
                const paymentResults = await createPayment(
                    token,
                    verificationToken
                );
                displayPaymentResults('SUCCESS');

                console.debug('Payment Success', paymentResults);
            } catch (e) {
                displayPaymentResults('FAILURE');
                console.error(e.message);
            }
        }

        $('.square-container').closest("form").submit(
            function (event) {
                event.preventDefault();
                handlePaymentMethodSubmission(card);
            }
        );
    } catch (error) {
        $(".square-errors").stop().hide().removeClass("sr-only");
        $(".square-errors").html("<div class='alert alert-danger'>Failed to load Square SDK</div>");
        $(".square-errors").slideDown();
        return;
    }
}

init();


async function initializeCard(payments) {
    const card = await payments.card();
    // clear elements before initializing
    $('#square-card').empty();
    await card.attach('#square-card');

    return card;
}

async function verifyBuyer(payments, token) {
    /* Get some data from the form */
    let amount = $('#square_card_total').val() / 100;
    let firstName = $('#id_payment_square-first_name').val();
    let lastName = $('#id_payment_square-last_name').val();
    let address1 = $('#id_payment_square-address_line_1').val();
    let address2 = $('#id_payment_square-address_line_2').val();
    let city = $('#id_payment_square-city').val();
    let state = $('#id_payment_square-state').val();
    let countryCode = $('#id_payment_square-country_code').val();

    /* Turn amount into string, e.g. 3500 -> '35.00' */
    amount = (amount / 100).toFixed(2);

    const verificationDetails = {
        amount: amount,
        billingContact: {
            givenName: firstName,
            familyName: lastName,
            addressLines: [address1, address2],
            city: city,
            state: state,
            countryCode: countryCode,
        },
        currencyCode: 'USD',
        intent: 'CHARGE',
    };

    const verificationResults = await payments.verifyBuyer(
        token.token,
        verificationDetails,
    );
    return verificationResults.token;
}

async function createPayment(token, verification) {
    $('#square_card_idempotency_token').val(window.crypto.randomUUID());
    $('#square_card_location_id').val(locationId);
    $('#square_card_source_id').val(token.token);
    $('#square_card_brand').val(token.details.card.brand);
    $('#square_card_last4').val(token.details.card.last4);
    $('#square_card_verification').val(verification);

    $('.square-container').closest("form").get(0).submit();
}

async function tokenize(paymentMethod) {
    const tokenResult = await paymentMethod.tokenize();
    if (tokenResult.status === 'OK') {
        return tokenResult;
    } else {
        let errorMessage = `Tokenization failed with status: ${tokenResult.status}`;
        if (tokenResult.errors) {
            errorMessage += ` and errors: ${JSON.stringify(
                tokenResult.errors,
            )}`;
        }

        throw new Error(errorMessage);
    }
}

// status is either SUCCESS or FAILURE;
function displayPaymentResults(status) {
    if (status === 'SUCCESS') {

    } else {
        $(".square-errors").stop().hide().removeClass("sr-only");
        $(".square-errors").html("<div class='alert alert-danger'>" + status + "</div>");
        $(".square-errors").slideDown();
    }
}