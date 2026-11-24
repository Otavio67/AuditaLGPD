// Acompanha a análise pelo servidor: mostra a etapa atual, preenche a barra e leva ao resultado.
(() => {
  const root = document.querySelector('.progress-page');
  if (!root) return;
  const poll = root.dataset.poll, home = root.dataset.home;
  const title = document.querySelector('#progress-title');
  const fill = document.querySelector('#progress-fill');
  const bar = document.querySelector('#progress-bar');
  const percentText = document.querySelector('#progress-percent');
  const log = document.querySelector('#progress-log');
  const errorBox = document.querySelector('#progress-error');
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

  let shown = 0, queue = [], draining = false, current = '', display = 0, ceiling = 3, ended = false, failures = 0;

  function setBar(value) {
    display = Math.max(display, Math.min(100, value));
    fill.style.width = display + '%';
    percentText.textContent = Math.round(display) + '%';
    bar.setAttribute('aria-valuenow', String(Math.round(display)));
  }

  function markDone(message) {
    const item = document.createElement('li');
    item.textContent = message;
    log.prepend(item);
  }

  // Mostra as etapas na ordem em que aconteceram, com um intervalo curto para as rápidas poderem ser lidas.
  async function drain() {
    if (draining) return;
    draining = true;
    while (queue.length) {
      const entry = queue.shift();
      if (current) markDone(current);
      current = entry.message;
      title.textContent = entry.message;
      ceiling = Math.max(entry.until || 0, entry.percent);
      setBar(entry.percent);
      await wait(queue.length ? Math.min(450, 2400 / (queue.length + 1)) : 0);
    }
    draining = false;
  }

  // Enquanto uma etapa demora, a barra avança devagar até perto do início da próxima, sem nunca chegar nela.
  const creep = setInterval(() => {
    if (ended || draining) return;
    const limit = ceiling - 1;
    if (display < limit) setBar(display + (limit - display) * 0.05 + 0.02);
  }, 300);

  function fail(message) {
    ended = true;
    clearInterval(creep);
    title.textContent = 'A análise não foi concluída';
    errorBox.textContent = message + ' ';
    const back = document.createElement('a');
    back.href = home;
    back.textContent = 'Voltar ao início';
    errorBox.append(back);
    errorBox.hidden = false;
  }

  async function finish(url) {
    ended = true;
    clearInterval(creep);
    while (draining || queue.length) await wait(100);
    if (current) markDone(current);
    current = '';
    title.textContent = 'Análise concluída. Abrindo o resultado';
    setBar(100);
    await wait(800);
    window.location.assign(url);
  }

  async function tick() {
    try {
      const response = await fetch(poll, {cache: 'no-store'});
      if (response.status === 404) return fail('Esta análise não está mais disponível. Inicie uma nova.');
      if (!response.ok) throw new Error('http');
      failures = 0;
      const state = await response.json();
      for (; shown < state.log.length; shown++) queue.push(state.log[shown]);
      drain();
      if (state.state === 'done') return finish(state.result_url);
      if (state.state === 'error') return fail(state.message);
    } catch (error) {
      if (++failures > 8) return fail('Não foi possível acompanhar a análise. Confira o histórico antes de tentar de novo.');
    }
    setTimeout(tick, 500);
  }
  tick();
})();
