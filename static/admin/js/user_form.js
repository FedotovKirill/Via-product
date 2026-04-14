(function () {
  /* --- Toast on return from save --- */
  var params = new URLSearchParams(window.location.search);
  if (params.get('saved') === '1') {
    if (typeof showToast === 'function') {
      showToast('Пользователь сохранён');
    }
    params.delete('saved');
    var newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
    window.history.replaceState({}, '', newUrl);
  }

  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('redmine_lookup_btn');
    var rid = document.getElementById('redmine_id');
    var dname = document.getElementById('display_name');
    var st = document.getElementById('redmine_lookup_status');
  var matrixDomain = document.body.getAttribute('data-matrix-domain') || '';
  var botTz = document.body.getAttribute('data-bot-tz') || '';

  function setStatus(msg) {
    if (st) st.textContent = msg || '';
  }

  var messages = {
    not_configured: 'Redmine не настроен (URL/API key).',
    not_found: 'Пользователь с таким ID не найден.',
    invalid_id: 'Введите положительный числовой ID.',
    cooldown: 'Поиск временно недоступен, подождите минуту.',
    timeout: 'Таймаут запроса к Redmine.',
    error: 'Ошибка запроса к Redmine.',
  };

  async function lookup() {
    if (!btn || !rid) return;
    var id = String(rid.value || '').trim();
    if (!id || !/^[1-9]\d*$/.test(id)) {
      setStatus(messages.invalid_id);
      return;
    }
    setStatus('Запрос…');
    btn.disabled = true;
    try {
      var r = await fetch('/redmine/users/lookup?user_id=' + encodeURIComponent(id), {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
      });
      var data = await r.json().catch(function () { return {}; });
      if (r.ok && data.ok && data.display_name) {
        if (dname) dname.value = data.display_name;
        if (data.login) {
          var roomInput = document.getElementById('room_localpart');
          if (roomInput && !roomInput.value) {
            roomInput.value = data.login;
            refreshSummary();
          }
        }
        setStatus(data.login ? (data.display_name + ' (' + data.login + ')') : data.display_name);
        refreshSummary();
      } else {
        var code = data.error || (r.status === 404 ? 'not_found' : 'error');
        setStatus(messages[code] || ('Ошибка: ' + (code || r.status)));
      }
    } catch (e) {
      setStatus(messages.error);
    } finally {
      btn.disabled = false;
    }
  }
  if (btn) btn.addEventListener('click', lookup);

  /* --- Test message --- */
  var testBtn = document.getElementById('test_message_btn');
  if (testBtn) {
    testBtn.addEventListener('click', async function () {
      var userId = testBtn.getAttribute('data-user-id');
      var roomInput = document.getElementById('room_localpart');
      var mxidLocalpart = roomInput ? roomInput.value.trim() : '';
      var mxid = mxidLocalpart
        ? ('@' + mxidLocalpart + (matrixDomain ? ':' + matrixDomain : ''))
        : '';

      if (!userId && !mxid) {
        setStatus('Укажите Matrix ID или сохраните пользователя');
        return;
      }

      testBtn.disabled = true;
      testBtn.textContent = '⏳ Отправка…';
      try {
        var csrf = (document.querySelector('input[name="csrf_token"]') || {}).value || '';
        var body = new FormData();
        if (userId) body.append('user_id', userId);
        if (mxid) body.append('mxid', mxid);
        var r = await fetch('/users/test-message', {
          method: 'POST',
          headers: { 'Accept': 'application/json', 'X-CSRF-Token': csrf },
          credentials: 'same-origin',
          body: body,
        });
        var data = await r.json().catch(function () { return {}; });
        if (data.ok) {
          setStatus('Сообщение доставлено');
        } else {
          setStatus('Не доставлено: ' + (data.error || 'неизвестная ошибка'));
        }
      } catch (e) {
        setStatus('Не доставлено: ошибка сети');
      } finally {
        testBtn.disabled = false;
        testBtn.textContent = 'Отправить тестовое сообщение';
      }
    });
  }

  /* --- Summary helpers --- */
  function textOrDash(v) {
    var value = String(v || '').trim();
    return value || '—';
  }
  function selectedText(selectEl) {
    if (!selectEl) return '—';
    var opt = selectEl.options[selectEl.selectedIndex];
    return opt ? (opt.textContent || '').trim() || '—' : '—';
  }
  function checkedLabels(selector) {
    return Array.from(document.querySelectorAll(selector))
      .filter(function (el) { return el.checked; })
      .map(function (el) { return String((el.parentElement || {}).textContent || '').trim(); })
      .filter(Boolean);
  }
  function selectedNotifyLabel() {
    var active = document.querySelector('input[name="status_preset"]:checked');
    if (!active) return '—';
    if (active.value === 'default') return 'По умолчанию';
    var labels = checkedLabels('input[name="status_values"]');
    return labels.length ? labels.join(', ') : '—';
  }
  function selectedVersionsLabel() {
    var active = document.querySelector('input[name="version_preset"]:checked');
    if (!active) return '—';
    if (active.value === 'default') return 'Все версии';
    var labels = checkedLabels('input[name="version_values"]');
    return labels.length ? labels.join(', ') : '—';
  }
  function selectedHours() {
    var from = document.getElementById('work_hours_from');
    var to = document.getElementById('work_hours_to');
    var fv = from ? String(from.value || '').trim() : '';
    var tv = to ? String(to.value || '').trim() : '';
    if (fv && tv) return fv + ' - ' + tv;
    return 'Не задано';
  }
  function dndLabel() {
    var dnd = document.getElementById('dnd');
    return dnd && dnd.checked ? 'Включено' : 'Выключено';
  }
  function setSummary(id, value) {
    var el = document.getElementById(id);
    if (!el) return;
    el.textContent = value;
    el.title = value && value !== '—' ? value : '';
  }
  function refreshSummary() {
    setSummary('summary_name', textOrDash((document.getElementById('display_name') || {}).value));
    setSummary('summary_group', selectedText(document.getElementById('group_id')));
    setSummary('summary_redmine_id', textOrDash((document.getElementById('redmine_id') || {}).value));
    var lp = (document.getElementById('room_localpart') || {}).value || '';
    var fullRoom = lp ? ('!' + lp + (matrixDomain ? ':' + matrixDomain : '')) : '';
    setSummary('summary_room', textOrDash(fullRoom));
    setSummary('summary_notify', selectedNotifyLabel());
    setSummary('summary_versions', selectedVersionsLabel());
    setSummary('summary_timezone', textOrDash((document.getElementById('timezone_name') || {}).value || botTz));
    setSummary('summary_hours', selectedHours());
    setSummary('summary_dnd', dndLabel());
  }

  /* --- Statuses toggle --- */
  (function () {
    var radios = Array.from(document.querySelectorAll('input[name="status_preset"]'));
    var box = document.getElementById('status_custom_box');
    var checkboxes = Array.from(document.querySelectorAll('input[name="status_values"]'));

    function setPreset(val) {
      var target = radios.find(function (r) { return r.value === val; });
      if (!target || target.checked) return;
      target.checked = true;
      // Триггерим change чтобы обновить UI
      var evt = new Event('change', { bubbles: true });
      target.dispatchEvent(evt);
    }

    function syncStatuses() {
      var current = radios.find(function (r) { return r.checked; });
      if (!current) return;
      // Панель всегда видна, меняем только чекбоксы
      if (current.value === 'default') {
        // Выбрать только те, что с data-default="true"
        checkboxes.forEach(function (cb) {
          cb.checked = cb.getAttribute('data-default') === 'true';
        });
      } else {
        checkboxes.forEach(function (cb) { cb.checked = false; });
      }
      refreshSummary();
    }

    function onCheckboxChange() {
      var current = radios.find(function (r) { return r.checked; });
      if (!current) return;
      // Проверяем все ли default-статусы выбраны
      var defaultChecked = checkboxes.filter(function (cb) { return cb.getAttribute('data-default') === 'true'; })
        .every(function (cb) { return cb.checked; });
      var nonDefaultChecked = checkboxes.filter(function (cb) { return cb.getAttribute('data-default') !== 'true'; })
        .every(function (cb) { return !cb.checked; });

      if (current.value === 'default' && !defaultChecked) {
        setPreset('custom');
      } else if (current.value === 'custom' && defaultChecked && nonDefaultChecked) {
        // Все выбраны (и default и non-default) → переключить на default
        setPreset('default');
      }
      refreshSummary();
    }

    radios.forEach(function (r) {
      r.addEventListener('change', function () { syncStatuses(); });
    });
    checkboxes.forEach(function (cb) {
      cb.addEventListener('change', onCheckboxChange);
    });
    syncStatuses();
  })();

  /* --- Versions toggle --- */
  (function () {
    var radios = Array.from(document.querySelectorAll('input[name="version_preset"]'));
    var box = document.getElementById('versions_custom_box');
    var choices = Array.from(document.querySelectorAll('input[name="version_values"]'));
    var hiddenJson = document.getElementById('version_keys_json');
    var hiddenText = document.getElementById('version_keys_text');
    var hiddenInitial = document.getElementById('initial_version_keys');
    function refreshBox() {
      var current = radios.find(function (r) { return r.checked; });
      if (!box) return;
      box.style.display = current && current.value === 'custom' ? 'block' : 'none';
    }
    function syncVersions() {
      var current = radios.find(function (r) { return r.checked; });
      var values = [];
      if (current && current.value === 'default') {
        values = choices.map(function (c) { return c.value.trim(); }).filter(Boolean);
      } else {
        values = choices.filter(function (c) { return c.checked; }).map(function (c) { return c.value.trim(); }).filter(Boolean);
      }
      if (hiddenJson) hiddenJson.value = JSON.stringify(values);
      var textValue = values.join(', ');
      if (hiddenText) hiddenText.value = textValue;
      if (hiddenInitial) hiddenInitial.value = textValue;
      refreshSummary();
    }
    radios.forEach(function (radio) {
      radio.addEventListener('change', function () { refreshBox(); syncVersions(); });
    });
    choices.forEach(function (choice) {
      choice.addEventListener('change', syncVersions);
    });
    refreshBox();
    syncVersions();
  })();

  /* --- Bind summary refresh --- */
  ['display_name', 'redmine_id', 'room_localpart', 'timezone_name', 'work_hours_from', 'work_hours_to', 'dnd', 'group_id'].forEach(function (id) {
    var el = document.getElementById(id);
    if (!el) return;
    var evt = (id === 'group_id' || id === 'dnd' || id === 'timezone_name') ? 'change' : 'input';
    el.addEventListener(evt, refreshSummary);
    if (evt !== 'change') {
      el.addEventListener('change', refreshSummary);
    }
  });
  Array.from(document.querySelectorAll('input[name="status_values"], input[name="status_preset"], input[name="version_values"], input[name="version_preset"]')).forEach(function (el) {
    el.addEventListener('change', refreshSummary);
  });
  refreshSummary();

  /* --- Form validation --- */
  var form = document.querySelector('.form');
  if (form) {
    form.addEventListener('submit', function (e) {
      var ridEl = document.getElementById('redmine_id');
      var roomEl = document.getElementById('room_localpart');
      var errors = [];

      if (ridEl && !ridEl.value.trim()) {
        errors.push('Укажите Redmine ID');
        ridEl.style.borderColor = '#f87171';
      } else if (ridEl) {
        ridEl.style.borderColor = '';
      }

      if (roomEl && !roomEl.value.trim()) {
        errors.push('Укажите Matrix ID');
        roomEl.style.borderColor = '#f87171';
      } else if (roomEl) {
        roomEl.style.borderColor = '';
      }

      if (errors.length) {
        e.preventDefault();
        if (typeof showToast === 'function') {
          showToast(errors.join('. '), true);
        }
      }
    });
  }

  /* --- Time input auto-format (24h, HH:MM) with strict validation --- */
  var TIME_RE = /^[0-2]\d:[0-5]\d$/;

  function validateTime(val) {
    if (!val || val.length < 4) return true; // incomplete — don't error yet
    if (!TIME_RE.test(val)) return false;
    var h = parseInt(val.substring(0, 2), 10);
    return h >= 0 && h <= 23;
  }

  document.querySelectorAll('input[name="work_hours_from"], input[name="work_hours_to"]').forEach(function (el) {
    el.addEventListener('input', function () {
      var val = el.value.replace(/[^\d:]/g, '');
      if (val.length === 2 && !val.includes(':')) {
        val = val + ':';
      }
      if (val.length > 5) val = val.substring(0, 5);
      el.value = val;
      el.classList.toggle('is-invalid', !validateTime(val));
    });
    el.addEventListener('blur', function () {
      var val = el.value.trim();
      if (!val) return;
      var m = val.match(/^(\d{1,2}):(\d{2})$/);
      if (!m) {
        el.value = '';
        el.classList.add('is-invalid');
        return;
      }
      var h = parseInt(m[1], 10);
      var min = parseInt(m[2], 10);
      if (h > 23 || min > 59) {
        el.value = '';
        el.classList.add('is-invalid');
        return;
      }
      el.value = String(h).padStart(2, '0') + ':' + String(min).padStart(2, '0');
      el.classList.remove('is-invalid');
    });
  });
  });
})();