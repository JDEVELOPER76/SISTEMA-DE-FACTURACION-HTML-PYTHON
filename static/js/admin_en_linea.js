let socketPanelEnLinea = null;
let cerrarPorLogout = false;

document.addEventListener('DOMContentLoaded', () => {
    conectarPanelEnLinea();
    configurarCierrePorLogout();
});

function conectarPanelEnLinea() {
    if (cerrarPorLogout) {
        return;
    }

    if (socketPanelEnLinea && socketPanelEnLinea.readyState === WebSocket.OPEN) {
        return;
    }

    const protocolo = location.protocol === 'https:' ? 'wss' : 'ws';
    socketPanelEnLinea = new WebSocket(`${protocolo}://${location.host}/ws/en_linea`);

    socketPanelEnLinea.addEventListener('message', (event) => {
        try {
            const data = JSON.parse(event.data);
            pintarUsuariosEnLinea(data);
        } catch (err) {
            console.error('Error leyendo datos de en línea:', err);
        }
    });

    // Si el socket se cae (ej. el server reinició), reintenta conectar.
    socketPanelEnLinea.addEventListener('close', () => {
        socketPanelEnLinea = null;
        if (cerrarPorLogout) {
            return;
        }
        setTimeout(conectarPanelEnLinea, 3000);
    });
}

function cerrarSocketPanelEnLinea() {
    cerrarPorLogout = true;

    if (socketPanelEnLinea && socketPanelEnLinea.readyState === WebSocket.OPEN) {
        socketPanelEnLinea.close(1000, 'Logout de administrador');
    }
    socketPanelEnLinea = null;
}

function configurarCierrePorLogout() {
    document.querySelectorAll('a[href="/logout"]').forEach((enlace) => {
        enlace.addEventListener('click', cerrarSocketPanelEnLinea, { capture: true });
    });

    window.addEventListener('pagehide', cerrarSocketPanelEnLinea);
    window.addEventListener('beforeunload', cerrarSocketPanelEnLinea);
}

function pintarUsuariosEnLinea(data) {
    const contador = document.getElementById('totalEnLinea');
    const cuerpoTabla = document.getElementById('cuerpoTablaEnLinea');
    const vacioMsg = document.getElementById('enLineaVacio');

    if (contador) contador.textContent = data.total ?? 0;
    if (!cuerpoTabla) return;

    const conectados = data.conectados || [];

    if (conectados.length === 0) {
        cuerpoTabla.innerHTML = '';
        if (vacioMsg) vacioMsg.style.display = 'block';
        return;
    }
    if (vacioMsg) vacioMsg.style.display = 'none';

    cuerpoTabla.innerHTML = conectados.map(u => `
        <tr>
            <td>
                <div class="item-meta">
                    <div class="en-linea-avatar">
                        ${u.foto ? `<img src="${u.foto}" alt="${u.nombre}">` : `<i class="fa-solid fa-user"></i>`}
                    </div>
                    <div class="item-info">
                        <strong>${u.nombre}</strong>
                        <span>@${u.username}</span>
                    </div>
                </div>
            </td>
            <td>${u.puesto || '-'}</td>
            <td>
                <span class="badge ${u.tipo === 'admin' ? 'badge-admin' : 'badge-user'}">
                    ${u.tipo === 'admin' ? 'Administrador' : 'Operario'}
                </span>
            </td>
            <td>
                <span class="en-linea-dot ${u.en_vivo ? 'vivo' : 'reciente'}"></span>
                ${u.en_vivo ? 'En línea' : 'Actividad reciente'}
            </td>
            <td>${u.ultima_actividad || '-'}</td>
        </tr>
    `).join('');
}
