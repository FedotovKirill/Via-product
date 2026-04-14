/**
 * Управление справочником статусов Redmine.
 * Три колонки: Все статусы | По умолчанию | Корзина
 * Drag-and-drop между колонками.
 */
(function () {
  'use strict';

  var allContainer = document.getElementById('statuses-all-items');
  var defaultContainer = document.getElementById('statuses-default-items');
  var trashContainer = document.getElementById('statuses-trash-items');
  var syncBtn = document.getElementById('sync-statuses-btn');
  var addNameInput = document.getElementById('status-add-name');
  var addBtn = document.getElementById('status-add-btn');

  var allStatuses = [];
  var csrfToken = '';

  function getCsrfToken() {
    if (csrfToken) return csrfToken;
    csrfToken = document.querySelector('input[name="csrf_token"]')?.value || '';
    return csrfToken;
  }

  async function loadStatuses() {
    try {
      var r = await fetch('/api/catalog/statuses', { credentials: 'same-origin' });
      if (!r.ok) { console.error('[statuses] API returned', r.status); return; }
      var data = await r.json();
      allStatuses = data.statuses || [];
      render();
    } catch (e) { console.error('[statuses] Failed to load:', e); }
  }

  function render() {
    if (!allContainer || !defaultContainer || !trashContainer) return;

    var active = allStatuses.filter(function (s) { return s.is_active !== false; });
    var isDefault = active.filter(function (s) { return s.is_default === true; });
    var notDefault = active.filter(function (s) { return s.is_default !== true; });
    var trashed = allStatuses.filter(function (s) { return s.is_active === false; });

    allContainer.innerHTML = notDefault.map(renderItem).join('');
    defaultContainer.innerHTML = isDefault.map(renderItem).join('');
    trashContainer.innerHTML = trashed.map(function (s) {
      return '<div class="status-item" draggable="true" data-id="' + s.id + '" data-name="' + escAttr(s.name) + '">' +
        '<span class="status-item-name">' + escHtml(s.name) + '</span>' +
        '<button type="button" class="status-item-del" data-action="restore" title="Восстановить">↩</button>' +
        '</div>';
    }).join('');

    updateCounts(isDefault.length, trashed.length);
    setupDragDrop();
  }

  function renderItem(s) {
    return '<div class="status-item" draggable="true" data-id="' + s.id + '" data-name="' + escAttr(s.name) + '">' +
      '<span class="status-item-name">' + escHtml(s.name) + '</span>' +
      '<button type="button" class="status-item-del" data-action="trash" title="В корзину">✕</button>' +
      '</div>';
  }

  function escHtml(s) { var d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
  function escAttr(s) { return (s || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }

  function updateCounts(defCount, trashCount) {
    var defEl = document.getElementById('statuses-default-count');
    var trashEl = document.getElementById('statuses-trash-count');
    if (defEl) { defEl.textContent = defCount; defEl.classList.toggle('visible', defCount > 0); }
    if (trashEl) { trashEl.textContent = trashCount; trashEl.classList.toggle('visible', trashCount > 0); }
  }

  // ── Toggle API ─────────────────────────────────────────────────

  function toggleField(id, field, cb) {
    fetch('/api/catalog/statuses/' + id + '/toggle?field=' + field, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRF-Token': getCsrfToken() },
      body: JSON.stringify({ csrf_token: getCsrfToken() }),
    }).then(function (r) { return r.json(); })
      .then(function (data) { if (data.ok) { loadStatuses(); if (cb) cb(); } });
  }

  function moveToTrash(id, name) {
    toggleField(id, 'is_active');
  }
  function restoreFromTrash(id) {
    toggleField(id, 'is_active');
  }
  function moveToDefault(id) {
    toggleField(id, 'is_default');
  }
  function removeFromDefault(id) {
    toggleField(id, 'is_default');
  }
  function permanentDelete(id) {
    showConfirm('Удалить статус навсегда? Он будет удалён у всех пользователей и групп.', function () {
      fetch('/api/catalog/statuses/' + id, {
        method: 'DELETE',
        credentials: 'same-origin',
        headers: { 'X-CSRF-Token': getCsrfToken() },
      }).then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok) {
            var msg = 'Статус удалён';
            if (data.affected_users) msg += ', затронуто пользователей: ' + data.affected_users;
            if (data.affected_groups) msg += ', групп: ' + data.affected_groups;
            showToastMsg(msg);
            loadStatuses();
          } else {
            showToastMsg(data.error || 'Ошибка', true);
          }
        });
    });
  }

  // ── Drag and Drop ──────────────────────────────────────────────

  var dragSrcEl = null;
  var dragDropInitialized = false;

  function setupDragDrop() {
    if (dragDropInitialized) return;
    dragDropInitialized = true;

    var zones = [allContainer, defaultContainer, trashContainer];
    zones.forEach(function (zone) {
      zone.addEventListener('dragstart', function (e) {
        var item = e.target.closest('.status-item');
        if (!item) return;
        dragSrcEl = item;
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', item.getAttribute('data-id'));
        item.classList.add('dragging');
      });
      zone.addEventListener('dragend', handleDragEnd);
      zone.addEventListener('dragover', handleDragOver);
      zone.addEventListener('dragleave', handleDragLeave);
      zone.addEventListener('drop', handleDrop);
    });

    // Button handlers
    allContainer.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-action="trash"]');
      if (!btn) return;
      var item = btn.closest('.status-item');
      if (item) moveToTrash(item.getAttribute('data-id'), item.getAttribute('data-name'));
    });
    defaultContainer.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-action="trash"]');
      if (!btn) return;
      var item = btn.closest('.status-item');
      if (item) moveToTrash(item.getAttribute('data-id'), item.getAttribute('data-name'));
    });
    trashContainer.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-action="restore"]');
      if (!btn) return;
      var item = btn.closest('.status-item');
      if (item) restoreFromTrash(item.getAttribute('data-id'));
    });

    trashContainer.addEventListener('dblclick', function (e) {
      var item = e.target.closest('.status-item');
      if (!item) permanentDelete(parseInt(item.getAttribute('data-id'), 10));
    });
  }

  function handleDragOver(e) {
    if (e.preventDefault) e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    this.classList.add('drag-over');
    return false;
  }
  function handleDragLeave() { this.classList.remove('drag-over'); }

  function handleDrop(e) {
    if (e.stopPropagation) e.stopPropagation();
    this.classList.remove('drag-over');
    if (!dragSrcEl) return false;

    var id = dragSrcEl.getAttribute('data-id');
    var name = dragSrcEl.getAttribute('data-name');
    var isAll = this === allContainer;
    var isDefault = this === defaultContainer;
    var isTrash = this === trashContainer;

    if (isTrash && !dragSrcEl.closest('.statuses-trash-col')) {
      moveToTrash(id, name);
    } else if (isAll && dragSrcEl.closest('.statuses-trash-col')) {
      restoreFromTrash(id);
    } else if (isDefault && dragSrcEl.closest('.statuses-all-col')) {
      moveToDefault(id);
    } else if (isAll && dragSrcEl.closest('.statuses-default-col')) {
      removeFromDefault(id);
    }
    return false;
  }

  function handleDragEnd() {
    if (dragSrcEl) dragSrcEl.classList.remove('dragging');
    dragSrcEl = null;
    document.querySelectorAll('.status-item').forEach(function (i) { i.classList.remove('dragging'); });
    document.querySelectorAll('.statuses-dropzone').forEach(function (z) { z.classList.remove('drag-over'); });
  }

  // ── Confirm / Toast ────────────────────────────────────────────

  function showConfirm(message, onOk) {
    var overlay = document.createElement('div');
    overlay.className = 'custom-confirm-overlay';
    overlay.innerHTML = '<div class="custom-confirm"><p>' + escHtml(message) + '</p>' +
      '<div class="custom-confirm-actions"><button type="button" class="btn btn-ghost" id="cc-cancel">Отмена</button>' +
      '<button type="button" class="btn btn-danger" id="cc-ok">Удалить</button></div></div>';
    document.body.appendChild(overlay);
    function close(r) { overlay.remove(); if (r) onOk(); }
    overlay.querySelector('#cc-cancel').addEventListener('click', function () { close(false); });
    overlay.querySelector('#cc-ok').addEventListener('click', function () { close(true); });
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(false); });
  }

  function showToastMsg(text, isError) {
    var t = document.createElement('div');
    t.className = 'custom-toast' + (isError ? ' custom-toast--error' : '');
    t.textContent = text;
    document.body.appendChild(t);
    requestAnimationFrame(function () { t.classList.add('show'); });
    setTimeout(function () { t.classList.remove('show'); setTimeout(function () { t.remove(); }, 400); }, 3000);
  }

  // ── Add status ─────────────────────────────────────────────────

  if (addBtn) {
    addBtn.addEventListener('click', async function () {
      var name = addNameInput.value.trim();
      if (!name) { showToastMsg('Введите название', true); return; }
      var fd = new FormData();
      fd.append('redmine_status_id', '0');
      fd.append('name', name);
      fd.append('csrf_token', getCsrfToken());
      try {
        var r = await fetch('/api/catalog/statuses', { method: 'POST', credentials: 'same-origin', body: fd });
        var data = await r.json();
        if (!r.ok) { showToastMsg(data.error || 'Ошибка', true); return; }
        addNameInput.value = '';
        allStatuses.push(data);
        render();
        showToastMsg('Статус добавлен');
      } catch (e) { showToastMsg('Ошибка сети: ' + e.message, true); }
    });
  }

  // ── Sync ──────────────────────────────────────────────────────

  if (syncBtn) {
    syncBtn.addEventListener('click', async function () {
      syncBtn.disabled = true;
      syncBtn.textContent = 'Синхронизация…';
      try {
        var r = await fetch('/api/catalog/sync-statuses', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': getCsrfToken() },
          body: JSON.stringify({ csrf_token: getCsrfToken() }),
        });
        var data = await r.json();
        if (!r.ok) { showToastMsg(data.error || 'Ошибка синхронизации', true); return; }
        var parts = [];
        parts.push(data.total + ' статусов');
        if (data.added) parts.push('+' + data.added);
        if (data.updated) parts.push('~' + data.updated);
        if (data.hidden) parts.push('−' + data.hidden + ' скрыто');
        showToastMsg('Статусы обновлены: ' + parts.join(', '));
        loadStatuses();
      } catch (e) { showToastMsg('Ошибка сети: ' + e.message, true); }
      finally { syncBtn.disabled = false; syncBtn.textContent = 'Обновить из Redmine'; }
    });
  }

  loadStatuses();
})();
