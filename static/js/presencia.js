/*
 * presencia.js
 * Se incluye en TODAS las páginas autenticadas (admin_*.html, empleado_*.html).
 * Abre un WebSocket a /ws/presencia mientras la pestaña esté abierta para que
 * el servidor sepa, al instante, quién está conectado y quién se desconectó.
 * No pinta nada en pantalla: solo mantiene viva la señal de presencia.
 */
(function () {
    const PING_INTERVALO_MS = 25000;
    const RECONEXION_INICIAL_MS = 1500;
    const RECONEXION_MAX_MS = 30000;

    let socket = null;
    let pingTimer = null;
    let intentosReconexion = 0;

    function conectar() {
        const protocolo = location.protocol === 'https:' ? 'wss' : 'ws';
        socket = new WebSocket(`${protocolo}://${location.host}/ws/presencia`);

        socket.addEventListener('open', () => {
            intentosReconexion = 0;
            clearInterval(pingTimer);
            pingTimer = setInterval(() => {
                if (socket.readyState === WebSocket.OPEN) {
                    socket.send('ping');
                }
            }, PING_INTERVALO_MS);
        });

        socket.addEventListener('close', () => {
            clearInterval(pingTimer);
            programarReconexion();
        });

        socket.addEventListener('error', () => {
            socket.close();
        });
    }

    function programarReconexion() {
        intentosReconexion++;
        const espera = Math.min(RECONEXION_INICIAL_MS * intentosReconexion, RECONEXION_MAX_MS);
        setTimeout(conectar, espera);
    }

    // Si la pestaña estaba en segundo plano y el socket se cayó, reconectar al volver.
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible' && (!socket || socket.readyState === WebSocket.CLOSED)) {
            conectar();
        }
    });

    conectar();
})();
