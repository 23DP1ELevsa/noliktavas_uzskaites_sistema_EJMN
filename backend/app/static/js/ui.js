// Bez JavaScript izvēlne paliek redzama, lai visas lapas būtu sasniedzamas.
document.documentElement.classList.add('js');
const toastTimers = new WeakMap();
document.querySelectorAll('[data-toast]').forEach((toast) => {
    const stack = toast.parentElement;
    toast.hidden = toast !== stack.querySelector('[data-toast]');
    const closeButton = toast.querySelector('.toast-close');
    let timer;
    let closing = false;
    const dismiss = () => {
        if (closing || toast.hidden) return;
        closing = true;
        clearTimeout(timer);
        toast.classList.add('is-leaving');
        window.setTimeout(() => {
            const restoreFocus = toast.contains(document.activeElement);
            toast.remove();
            const next = stack.querySelector('[data-toast]');
            if (next) {
                next.hidden = false;
                if (restoreFocus) next.querySelector('.toast-close').focus();
                toastTimers.get(next)?.();
            } else stack.remove();
        }, window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 600);
    };
    const resume = () => {
        clearTimeout(timer);
        if (!toast.hidden && !closing) {
            const duration = Math.min(10000, Math.max(5000, toast.querySelector('span').textContent.length * 55));
            timer = window.setTimeout(dismiss, duration);
        }
    };
    closeButton.hidden = false;
    closeButton.addEventListener('click', dismiss);
    toastTimers.set(toast, resume);
    resume();
});
const navigationToggle = document.querySelector('.nav-toggle');
const navigation = document.querySelector('#site-navigation');
const setNavigationOpen = (open) => {
    navigationToggle?.setAttribute('aria-expanded', String(open));
    navigationToggle?.setAttribute('aria-label', open ? 'Aizvērt izvēlni' : 'Atvērt izvēlni');
    navigation?.classList.toggle('is-open', open);
};
navigationToggle?.addEventListener('click', () => {
    setNavigationOpen(navigationToggle.getAttribute('aria-expanded') !== 'true');
});
// Klikšķis ārpus galvenes aizver paneli; saites saglabā parasto pārlūka darbību.
document.addEventListener('click', (event) => {
    if (!event.target.closest('.market-header')) setNavigationOpen(false);
});
navigation?.addEventListener('click', (event) => {
    if (event.target.closest('a')) setNavigationOpen(false);
});
document.addEventListener('focusin', (event) => {
    if (!event.target.closest('.market-header')) setNavigationOpen(false);
});
document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && navigationToggle?.getAttribute('aria-expanded') === 'true') {
        setNavigationOpen(false);
        navigationToggle.focus();
    }
});
window.matchMedia('(min-width: 901px)').addEventListener('change', () => setNavigationOpen(false));

// Sadaļas aizveram tikai mobilajā skatā; saturs un ievadītie dati paliek dokumentā.
const mobileSections = window.matchMedia('(max-width: 760px)');
document.querySelectorAll('[data-mobile-section]').forEach((section) => {
    const toggle = section.querySelector('[data-mobile-toggle]');
    const content = document.getElementById(toggle.getAttribute('aria-controls'));
    const setOpen = (open) => {
        toggle.setAttribute('aria-expanded', String(open));
        section.classList.toggle('is-open', open);
    };
    if (window.location.hash === `#${content.id}`) setOpen(true);
    toggle.addEventListener('click', () => setOpen(toggle.getAttribute('aria-expanded') !== 'true'));
    section.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && mobileSections.matches && toggle.getAttribute('aria-expanded') === 'true') {
            setOpen(false);
            toggle.focus();
        }
    });
    mobileSections.addEventListener('change', () => {
        const focusInside = content.contains(document.activeElement);
        setOpen(false);
        if (mobileSections.matches && focusInside) toggle.focus();
        else if (!mobileSections.matches && document.activeElement === toggle) {
            content.querySelector('a, button, input, select')?.focus();
        }
    });
});

// Saglabājam pārlūka ievades pārbaudi, bet kļūdas paskaidrojam latviski.
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
    else if (state.patternMismatch) message = control.matches('[data-password-input]')
        ? 'Parolei vajag vismaz 8 rakstzīmes, 1 lielo burtu un 1 speciālo simbolu.'
        : 'Ievadiet datus norādītajā formātā.';
    control.setCustomValidity(message);
}, true);
for (const eventName of ['input', 'change']) {
    document.addEventListener(eventName, (event) => event.target.setCustomValidity?.(''));
}

// Prasības atjaunojam rakstīšanas un ielīmēšanas laikā, arī dzēšot jau ievadīto.
const passwordInput = document.querySelector('[data-password-input]');
if (passwordInput) {
    const updatePasswordRequirements = () => {
        const value = passwordInput.value;
        const rules = {
            length: [...value].length >= 8,
            uppercase: /\p{Lu}/u.test(value),
            special: /[\p{P}\p{S}]/u.test(value),
        };
        document.querySelectorAll('[data-password-rule]').forEach((item) => {
            const passed = rules[item.dataset.passwordRule];
            const icon = passed ? '✓' : '×';
            if (item.querySelector('[data-rule-icon]').textContent === icon) return;
            item.classList.toggle('is-met', passed);
            item.querySelector('[data-rule-icon]').textContent = icon;
            item.querySelector('[data-rule-status]').textContent = passed ? 'Izpildīts: ' : 'Nav izpildīts: ';
        });
    };
    passwordInput.addEventListener('input', updatePasswordRequirements);
    passwordInput.addEventListener('change', updatePasswordRequirements);
    window.addEventListener('pageshow', updatePasswordRequirements);
    updatePasswordRequirements();
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
