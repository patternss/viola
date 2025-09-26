(function(){
  const messagesEl = document.getElementById('messages');
  const form = document.getElementById('messageForm');
  const inputText = document.getElementById('inputText');
  const tutorToolInputs = Array.from(document.querySelectorAll('input[name="tutor_tool"]'));
  const topicSelect = document.getElementById('topicSelect');
  const modelSelect = document.getElementById('modelSelect');

  if (!form || !inputText || !messagesEl) {
    console.warn('app.js: missing expected DOM elements');
    return;
  }

  let token = null;

  async function fetchToken(){
    try{
      const res = await fetch('/api/token');
      const j = await res.json();
      token = j.token;
    }catch(e){
      console.error('fetchToken error', e);
    }
  }

  const messages = [];

  // create custom select widget for consistent styling
  function createCustomSelect(selectEl){
    if(!selectEl) return null;
    selectEl.classList.add('native-hidden');

    const wrapper = document.createElement('div');
    wrapper.className = 'custom-select';

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'select-btn';
    btn.textContent = selectEl.options[selectEl.selectedIndex]?.text || selectEl.placeholder || '';

    const opts = document.createElement('div');
    opts.className = 'options';
    opts.style.display = 'none';

    Array.from(selectEl.options).forEach((opt)=>{
      const div = document.createElement('div');
      div.className = 'option' + (opt.selected ? ' selected' : '');
      div.textContent = opt.text;
      div.dataset.value = opt.value;
      div.addEventListener('click', ()=>{
        // update native select
        selectEl.value = opt.value;
        // update button text
        btn.textContent = opt.text;
        // close options
        opts.style.display = 'none';
        Array.from(opts.children).forEach(c=>c.classList.remove('selected'));
        div.classList.add('selected');
        selectEl.dispatchEvent(new Event('change'));
      });
      opts.appendChild(div);
    });

    btn.addEventListener('click', ()=>{
      opts.style.display = opts.style.display === 'none' ? 'block' : 'none';
    });

    wrapper.appendChild(btn);
    wrapper.appendChild(opts);
    selectEl.parentNode.insertBefore(wrapper, selectEl.nextSibling);
    return wrapper;
  }

  // instantiate custom selects for topic and model
  const topicCustom = createCustomSelect(topicSelect);
  const modelCustom = createCustomSelect(modelSelect);

  // When topic changes, restart the chat and request a startup message
  async function fetchWithBackoff(url, maxAttempts = 5, baseDelay = 500){
    let attempt = 0;
    while(attempt < maxAttempts){
      attempt++;
      try{
        const res = await fetch(url);
        if(res.status === 503){
          // Backoff and retry
          const jitter = Math.random() * 200;
          const delay = baseDelay * Math.pow(2, attempt - 1) + jitter;
          await new Promise(r => setTimeout(r, delay));
          continue;
        }
        return res;
      }catch(err){
        // network or other error - apply backoff and retry
        const jitter = Math.random() * 200;
        const delay = baseDelay * Math.pow(2, attempt - 1) + jitter;
        await new Promise(r => setTimeout(r, delay));
      }
    }
    throw new Error('Max retry attempts reached');
  }


  async function handleTopicChange(){
    const topic = topicSelect ? topicSelect.value : '';
    // clear local messages
    messages.length = 0;
    messagesEl.innerHTML = '';
    try{
      const res = await fetchWithBackoff(`/api/startup-message?topic=${encodeURIComponent(topic)}`);
      const j = await res.json();
      if(res.ok){
        messages.push({ role: 'assistant', content: j.reply });
        addMessage('assistant', j.reply);
      }else{
        addMessage('error', j.detail || JSON.stringify(j));
      }
    }catch(err){
      addMessage('error', err && err.message ? err.message : String(err));
    }
  }

  if(topicSelect){
    topicSelect.addEventListener('change', handleTopicChange);
  }

  // Close custom selects when clicking outside
  document.addEventListener('click', (e)=>{
    Array.from(document.querySelectorAll('.custom-select .options')).forEach(opts=>{
      if(!opts.parentNode.contains(e.target)) opts.style.display = 'none';
    });
  });

  function addMessage(role, text){
    const li = document.createElement('li');
    const cls = role === 'user' ? 'user' : (role === 'assistant' ? 'assistant' : '');
    li.className = cls;

    if(role === 'assistant'){
      // Create avatar element on the left
      const avatarWrap = document.createElement('div');
      avatarWrap.className = 'avatar';
      const img = document.createElement('img');
      img.src = '/images/viola_thumbnail.png';
      // Fallback to a tiny inline SVG avatar if the PNG fails to load
      img.onerror = function(){
        this.onerror = null;
        this.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"><rect rx="6" width="100%" height="100%" fill="%2360a5fa"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-size="18" fill="white">V</text></svg>';
      };
      img.alt = 'Viola';
      avatarWrap.appendChild(img);

      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.textContent = text;

      li.appendChild(avatarWrap);
      li.appendChild(bubble);
    } else {
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.textContent = text;
      li.appendChild(bubble);
    }

    messagesEl.appendChild(li);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  form.addEventListener('submit', async function(e){
    e.preventDefault();
    const role = 'user';
    const text = inputText.value && inputText.value.trim();
    if(!text) return;

    // Handle !restart command
    if(text === '!restart'){
      // Clear messages and restart session
      messages.length = 0;
      messagesEl.innerHTML = '';
      inputText.value = '';
      inputText.focus();
      // Request new startup message
      await handleTopicChange();
      return;
    }

    addMessage(role, text);
    messages.push({ role, content: text });

    inputText.value = '';
    inputText.focus();

    const selectedTools = tutorToolInputs.filter(i=>i.checked).map(i=>i.value);
    const payload = {
      messages: messages.slice(),
      token,
      tutor_tools: selectedTools,
      topic: topicSelect ? topicSelect.value : null,
      model: modelSelect ? modelSelect.value : null,
    };
    try{
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const j = await res.json();
      if(res.ok){
        messages.push({ role: 'assistant', content: j.reply });
        addMessage('assistant', j.reply);
      }else{
        addMessage('error', j.detail || JSON.stringify(j));
      }
    }catch(err){
      addMessage('error', err && err.message ? err.message : String(err));
    }
  });

  fetchToken();
  // request initial startup message on load
  (async ()=>{ if(topicSelect) await handleTopicChange(); })();
})();
