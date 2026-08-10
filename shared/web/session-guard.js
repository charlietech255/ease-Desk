// ease-Desk Session Guard
// This script is injected by Nginx at the very top of KasmVNC's <head>.
// It ensures that KasmVNC receives the password required for VNC authentication
// without exposing it in the browser's address bar.

(function() {
    var token = sessionStorage.getItem('easedesk_session');
    var pw = sessionStorage.getItem('easedesk_pass');

    if (!token || !pw) {
        // No session token -> user didn't come from login page or refreshed a stale tab
        window.location.replace('/');
        return;
    }

    // Session present — read and clear so next refresh forces login
    sessionStorage.removeItem('easedesk_session');
    sessionStorage.removeItem('easedesk_user');
    sessionStorage.removeItem('easedesk_pass');

    // Inject credentials into the URL so KasmVNC's JS can read them for VNC auth
    var u = new URL(window.location.href);
    u.searchParams.set('password', pw);
    u.searchParams.set('autoconnect', 'true');
    
    // Use replaceState to update the URL without triggering a reload,
    // so KasmVNC sees the parameters but the user doesn't easily copy them.
    window.history.replaceState({}, '', u.toString());
})();
