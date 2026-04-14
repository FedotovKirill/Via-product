/**
 * Показывает/скрывает блок кастомных статусов
 * в зависимости от выбранного radio[name="status_preset"].
 * "Все статусы" — выделяет все чекбоксы.
 * "Выбрать статусы" — сбрасывает выбор.
 * Авто-свитч при изменении чекбоксов.
 *
 * Использование: initStatusToggle('status_custom_box')
 */
function initStatusToggle(boxId) {
  var radios = Array.from(document.querySelectorAll('input[name="status_preset"]'));
  var checkboxes = Array.from(document.querySelectorAll('input[name="status_values"]'));
  var box = document.getElementById(boxId);
  if (!radios.length) return;

  function setPreset(val) {
    var target = radios.find(function (r) { return r.value === val; });
    if (!target || target.checked) return;
    target.checked = true;
    var evt = new Event('change', { bubbles: true });
    target.dispatchEvent(evt);
  }

  function sync() {
    var current = radios.find(function (r) { return r.checked; });
    if (!current) return;
    if (current.value === 'default') {
      checkboxes.forEach(function (cb) {
        cb.checked = cb.getAttribute('data-default') === 'true';
      });
    } else {
      checkboxes.forEach(function (cb) { cb.checked = false; });
    }
  }

  function onCheckboxChange() {
    var current = radios.find(function (r) { return r.checked; });
    if (!current) return;
    var defaultChecked = checkboxes.filter(function (cb) { return cb.getAttribute('data-default') === 'true'; })
      .every(function (cb) { return cb.checked; });
    var nonDefaultChecked = checkboxes.filter(function (cb) { return cb.getAttribute('data-default') !== 'true'; })
      .every(function (cb) { return !cb.checked; });

    if (current.value === 'default' && !defaultChecked) {
      setPreset('custom');
    } else if (current.value === 'custom' && defaultChecked && nonDefaultChecked) {
      setPreset('default');
    }
  }

  radios.forEach(function (r) { r.addEventListener('change', function () { sync(); }); });
  checkboxes.forEach(function (cb) { cb.addEventListener('change', onCheckboxChange); });
  sync();
}
