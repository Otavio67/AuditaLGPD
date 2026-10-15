const form = document.querySelector('#audit-form');
if (form) {
  form.addEventListener('submit', () => {
    const button = document.querySelector('#submit-audit');
    button.disabled = true;
    button.textContent = 'Analisando…';
    document.querySelector('#progress').textContent = 'Consultando a página. Aguarde o término da análise.';
    form.setAttribute('aria-busy', 'true');
  });
}
