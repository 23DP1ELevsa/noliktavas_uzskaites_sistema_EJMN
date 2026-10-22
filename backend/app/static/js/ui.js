// Navigation remains available without JavaScript.
document.documentElement.classList.add('js');
document.querySelectorAll('[data-toast]').forEach((toast) => {
    const closeButton = toast.querySelector('.toast-close');
    let timer;
    let closing = false;
    const dismiss = () => {
        if (closing) return;
        closing = true;
        clearTimeout(timer);
        toast.classList.add('is-leaving');
        window.setTimeout(() => {
            const stack = toast.parentElement;
            toast.remove();
            if (!stack.children.length) stack.remove();
        }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 600);
    };
    const pause = () => clearTimeout(timer);
    const resume = () => {
        pause();
        if (!closing && !toast.matches(':hover') && !toast.contains(document.activeElement)) {
            timer = window.setTimeout(dismiss, 3000);
        }
    };
    closeButton.hidden = false;
    closeButton.addEventListener('click', dismiss);
    toast.addEventListener('mouseenter', pause);
    toast.addEventListener('mouseleave', resume);
    toast.addEventListener('focusin', pause);
    toast.addEventListener('focusout', () => window.setTimeout(resume, 0));
    resume();
});
const navigationToggle = document.querySelector('.nav-toggle');
const navigation = document.querySelector('#site-navigation');
const setNavigationOpen = (open) => {
    navigationToggle?.setAttribute('aria-expanded', String(open));
    navigation?.classList.toggle('is-open', open);
};
navigationToggle?.addEventListener('click', () => {
    setNavigationOpen(navigationToggle.getAttribute('aria-expanded') !== 'true');
});
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && navigationToggle?.getAttribute('aria-expanded') === 'true') {
        setNavigationOpen(false);
        navigationToggle.focus();
    }
});
window.matchMedia('(min-width: 901px)').addEventListener('change', () => setNavigationOpen(false));

// Keep native constraint validation and present its messages in Latvian.
document.addEventListener('invalid', (event) => {
    const control = event.target;
    if (!control.setCustomValidity) return;
    control.setCustomValidity('');
    const state = control.validity;
    let message = 'Pārbaudiet ievadīto vērtību.';
    if (state.valueMissing) message = control.type === 'file' ? 'Lūdzu, izvēlieties failu.' : 'Lūdzu, aizpildiet šo lauku.';
    else if (state.typeMismatch) message = control.type === 'email' ? 'Ievadiet derīgu e-pasta adresi.' : 'Ievadiet derīgu tīmekļa adresi.';
    else if (state.rangeUnderflow) message = `Minimālā vērtība ir ${control.min}.`;
    else if (state.rangeOverflow) message = `Maksimālā vērtība ir ${control.max}.`;
    else if (state.tooShort) message = `Ievadiet vismaz ${control.minLength} rakstzīmes.`;
    else if (state.tooLong) message = `Ievadiet ne vairāk kā ${control.maxLength} rakstzīmes.`;
    else if (state.stepMismatch) message = control.step === '1' ? 'Ievadiet veselu skaitli.' : 'Ievadiet vērtību ar norādīto soli.';
    else if (state.badInput) message = 'Ievadiet derīgu skaitli.';
    else if (state.patternMismatch) message = 'Ievadiet datus norādītajā formātā.';
    control.setCustomValidity(message);
}, true);
for (const eventName of ['input', 'change']) {
    document.addEventListener(eventName, (event) => event.target.setCustomValidity?.(''));
}
document.querySelectorAll('[data-file-picker]').forEach((input) => {
    input.addEventListener('change', () => {
        input.closest('.file-upload-field').querySelector('[data-file-name]').textContent = input.files[0]?.name || 'Fails nav izvēlēts';
    });
});

const confirmationDialog = document.querySelector('[data-confirm-dialog]');
if (confirmationDialog) {
    let pendingForm = null;
    let confirmedForm = null;
    document.querySelectorAll('[data-confirm-delete]').forEach((button) => {
        button.form.addEventListener('submit', (event) => {
            if (confirmedForm === button.form) { confirmedForm = null; return; }
            event.preventDefault();
            pendingForm = button.form;
            confirmationDialog.showModal();
        });
    });
    confirmationDialog.querySelector('[data-confirm-cancel]').addEventListener('click', () => confirmationDialog.close());
    confirmationDialog.addEventListener('close', () => { pendingForm = null; });
    confirmationDialog.querySelector('[data-confirm-accept]').addEventListener('click', () => {
        const form = pendingForm;
        if (!form) return;
        confirmedForm = form;
        confirmationDialog.close();
        form.requestSubmit();
    });
}
document.querySelectorAll('img[data-admin-image]').forEach((image) => {
    const fallback = () => {
        image.hidden = true;
        const placeholder = image.parentElement.querySelector('.image-fallback');
        if (placeholder) placeholder.hidden = false;
    };
    image.addEventListener('error', fallback, { once: true });
    if (image.complete && !image.naturalWidth) fallback();
});
