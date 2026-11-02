/* site.js: page behaviour for the Consult site (index.html). Removes the no-js class, runs the
   install tabs (switched together across install blocks, with arrow-key support), and runs the
   copy buttons, announcing results to screen readers. The wordmark animation is in wordmark.js
   and the skills-page rail in rail.js. */
(function () {
  'use strict';

  document.documentElement.classList.remove('no-js');

  /* Tabs switch together across every install block on the page. */
  var allTabs = Array.prototype.slice.call(document.querySelectorAll('[role="tab"]'));
  function selectKey(key) {
    allTabs.forEach(function (t) {
      var on = t.getAttribute('data-key') === key;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute('aria-controls')).hidden = !on;
    });
  }
  function nextIndex(key, i, count) {
    if (key === 'ArrowRight') return (i + 1) % count;
    if (key === 'ArrowLeft') return (i - 1 + count) % count;
    if (key === 'Home') return 0;
    if (key === 'End') return count - 1;
    return null;
  }
  Array.prototype.forEach.call(document.querySelectorAll('[role="tablist"]'), function (list) {
    var tabs = Array.prototype.slice.call(list.querySelectorAll('[role="tab"]'));
    tabs.forEach(function (tab, i) {
      tab.addEventListener('click', function () { selectKey(tab.getAttribute('data-key')); });
      tab.addEventListener('keydown', function (e) {
        var j = nextIndex(e.key, i, tabs.length);
        if (j === null) return;
        e.preventDefault();
        selectKey(tabs[j].getAttribute('data-key'));
        tabs[j].focus();
      });
    });
  });
  if (allTabs.length) selectKey('code');

  /* Copy buttons: copy the named element's text, or select it when the clipboard is refused. */
  var status = document.createElement('p');
  status.className = 'vh';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  document.body.appendChild(status);
  function announce(message) {
    status.textContent = '';
    window.setTimeout(function () { status.textContent = message; }, 50);
  }
  function selectText(el) {
    var range = document.createRange();
    range.selectNodeContents(el);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }
  function showResult(btn, label, ok, source) {
    var visible = btn.firstChild;
    if (ok) {
      visible.nodeValue = 'Copied';
      announce('Copied: ' + source.textContent);
    } else {
      selectText(source);
      visible.nodeValue = 'Selected';
      announce('Copy was blocked. The text is selected; press Ctrl+C or Command+C to copy it.');
    }
    window.setTimeout(function () { visible.nodeValue = label; }, 2000);
  }
  Array.prototype.forEach.call(document.querySelectorAll('[data-copy]'), function (btn) {
    var label = btn.firstChild.nodeValue;
    btn.addEventListener('click', function () {
      var source = document.getElementById(btn.getAttribute('data-copy'));
      if (!navigator.clipboard || !navigator.clipboard.writeText) { showResult(btn, label, false, source); return; }
      navigator.clipboard.writeText(source.textContent.trim()).then(
        function () { showResult(btn, label, true, source); },
        function () { showResult(btn, label, false, source); }
      );
    });
  });
})();
