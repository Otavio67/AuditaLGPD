const form = document.querySelector('#audit-form');
if (form && window.fetch) {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = document.querySelector('#submit-audit');
    const progress = document.querySelector('#progress');
    const errorBox = document.querySelector('#form-error');
    button.disabled = true;
    button.textContent = 'Analisando…';
    errorBox.hidden = true;
    form.setAttribute('aria-busy', 'true');
    try {
      const response = await fetch(form.action, {method:'POST', body:new FormData(form), headers:{'X-Audita-Async':'1'}});
      if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('A sessão expirou ou a solicitação não foi aceita. Atualize a página e tente novamente.');
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível iniciar a análise.');
      while (true) {
        const stateResponse = await fetch(data.progress_url, {cache:'no-store'});
        if (!stateResponse.ok) throw new Error('Não foi possível acompanhar a análise. Confira o histórico antes de tentar novamente.');
        const state = await stateResponse.json();
        progress.textContent = state.message;
        if (state.state === 'done') {window.location.assign(state.result_url); return;}
        if (state.state === 'error') throw new Error(state.message);
        await new Promise(resolve => setTimeout(resolve, 1800));
      }
    } catch (error) {
      errorBox.textContent = error.message || 'Conexão interrompida. Confira o histórico local.';
      errorBox.hidden = false;
      button.disabled = false;
      button.textContent = 'Analisar privacidade →';
      progress.textContent = 'Você pode corrigir a solicitação e tentar novamente.';
      form.removeAttribute('aria-busy');
    }
  });
}
const resultFilter = document.querySelector('#result-filter');
if (resultFilter) {
  resultFilter.addEventListener('change', () => {
    let visible = 0;
    document.querySelectorAll('[data-check-status]').forEach(card => {
      card.hidden = resultFilter.value !== 'all' && card.dataset.checkStatus !== resultFilter.value;
      if (!card.hidden) visible++;
    });
    document.querySelector('#filter-empty').hidden = visible !== 0;
  });
}
