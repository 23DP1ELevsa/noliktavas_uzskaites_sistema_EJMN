document.querySelectorAll('[data-cart-image]').forEach((image) => {
    const showFallback = () => {
        image.hidden = true;
        image.parentElement.querySelector('.image-fallback').hidden = false;
    };
    image.addEventListener('error', showFallback, { once: true });
    if (image.complete && !image.naturalWidth) showFallback();
});

document.querySelectorAll('.cart-quantity-form').forEach((form) => {
    form.addEventListener('submit', () => {
        const input = form.querySelector('input[name="quantity"]');
        input.value = String(input.valueAsNumber);
    });
});
