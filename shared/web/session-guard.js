/**
 * ease-Desk Session Guard
 * Injected into KasmVNC's <head> by Nginx sub_filter.
 *
 * Flow:
 *  - Login page stores session token + VNC password in sessionStorage
 *  - This script runs before KasmVNC's own JS
 *  - If no session → redirect to login (covers refresh too)
 *  - If session → inject password + autoconnect into URL params
 *    then clear sessionStorage (next refresh = back to login)
 */
!function () {
  var s = sessionStorage.getItem('easedesk_session');
  if (!s) {
    // No active session — redirect to login page
    window.location.replace('/');
    return;
  }

  // Session present — read and immediately clear so next refresh forces login
  var pw   = sessionStorage.getItem('easedesk_pass') || '';
  sessionStorage.removeItem('easedesk_session');
  sessionStorage.removeItem('easedesk_user');
  sessionStorage.removeItem('easedesk_pass');

  // Inject VNC password + autoconnect flags into the URL so KasmVNC
  // reads them when its own scripts initialise.
  if (pw) {
    var u = new URL(window.location.href);
    u.searchParams.set('password',    pw);
    u.searchParams.set('autoconnect', 'true');
    u.searchParams.set('resize',      'scale');
    history.replaceState(null, '', u.toString());

    // Remove password from URL after KasmVNC has had time to read it
    setTimeout(function () {
      history.replaceState(null, '', window.location.pathname);
    }, 3000);
  }
}();
