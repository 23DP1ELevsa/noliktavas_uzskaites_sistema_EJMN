// The comparison and cart also work without JavaScript.
document.querySelectorAll('[data-local-time]').forEach((element) => {
    const date = new Date(element.dateTime);
    if (!Number.isNaN(date.getTime())) {
        element.textContent = new Intl.DateTimeFormat('lv-LV', {
            dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Riga',
        }).format(date) + ' (Rīgas laiks)';
    }
});

const form = document.querySelector('#comparison-form');
form?.querySelectorAll('input, select').forEach((control) => {
    control.addEventListener('change', () => {
        if (form.reportValidity()) form.requestSubmit();
    });
});

document.querySelectorAll('[data-product-image]').forEach((image) => {
    const showFallback = () => {
        image.hidden = true;
        image.parentElement.querySelector('.image-fallback').hidden = false;
    };
    image.addEventListener('error', showFallback, { once: true });
    if (image.complete && !image.naturalWidth) showFallback();
});

document.querySelectorAll('.offer-order-form').forEach((orderForm) => {
    const quantityInput = orderForm.querySelector('input[name="quantity"]');
    const preview = orderForm.querySelector('.order-total-preview');
    if (!preview) return;

    // Integer cents keep the displayed quote consistent with the server's Decimal prices.
    const toCents = (price) => BigInt(price.replace('.', ''));
    const unitPrice = toCents(orderForm.dataset.unitPrice);
    const deliveryPrice = toCents(orderForm.dataset.deliveryPrice);
    const updateTotal = () => {
        if (!quantityInput.validity.valid) {
            preview.hidden = true;
            return;
        }
        const cents = unitPrice * BigInt(quantityInput.valueAsNumber) + deliveryPrice;
        preview.querySelector('[data-order-total]').textContent =
            `${cents / 100n}.${String(cents % 100n).padStart(2, '0')} €`;
        preview.hidden = false;
    };
    quantityInput.addEventListener('input', updateTotal);
    orderForm.addEventListener('submit', () => {
        // Native number inputs also accept notation such as 1e1; submit whole digits.
        quantityInput.value = String(quantityInput.valueAsNumber);
    });
    updateTotal();
});
