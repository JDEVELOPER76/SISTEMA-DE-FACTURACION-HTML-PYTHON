document.addEventListener('DOMContentLoaded', () => {
    initEdicionPerfil();
    initSubidaFoto();
    conectarCompañerosEnLinea();
    verificarEstadoEscaner();

    // El escáner no tiene push en tiempo real todavía, así que se sigue verificando por polling
    setInterval(verificarEstadoEscaner, 10000);
});

function mostrarToast(mensaje, esError = false) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = mensaje;
    toast.classList.toggle('error', esError);
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2800);
}

/* ---------- Editar nombre / puesto ---------- */
function initEdicionPerfil() {
    const btnEditar = document.getElementById('btnEditarPerfil');
    const btnCancelar = document.getElementById('btnCancelarEdicion');
    const form = document.getElementById('perfilEditForm');

    if (!btnEditar || !form) return;

    btnEditar.addEventListener('click', () => {
        form.classList.toggle('visible');
    });

    btnCancelar.addEventListener('click', () => {
        form.classList.remove('visible');
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const nombre = document.getElementById('inputNombre').value.trim();
        const puesto = document.getElementById('inputPuesto').value.trim();

        if (!nombre) {
            mostrarToast('El nombre no puede estar vacío', true);
            return;
        }

        try {
            const formData = new FormData();
            formData.append('nombre', nombre);
            formData.append('puesto', puesto);

            const resp = await fetch('/api/perfil/editar', {
                method: 'POST',
                body: formData
            });

            if (!resp.ok) throw new Error('No se pudo guardar');

            document.getElementById('perfilNombre').textContent = nombre;
            document.getElementById('perfilPuesto').textContent = puesto || 'Sin puesto asignado';
            form.classList.remove('visible');
            mostrarToast('Perfil actualizado correctamente');
        } catch (err) {
            mostrarToast('Error al actualizar el perfil', true);
        }
    });
}

/* ---------- Subir foto de perfil ---------- */
function initSubidaFoto() {
    const input = document.getElementById('fotoInput');
    if (!input) return;

    input.addEventListener('change', async () => {
        const archivo = input.files[0];
        if (!archivo) return;

        const formData = new FormData();
        formData.append('imagen_archivo', archivo);

        try {
            const resp = await fetch('/api/perfil/foto', {
                method: 'POST',
                body: formData
            });
            const data = await resp.json();

            if (!resp.ok || !data.success) throw new Error(data.detail || 'Error');

            const avatarBox = document.getElementById('avatarPreview');
            avatarBox.innerHTML = `<img src="${data.foto}?t=${Date.now()}" alt="Foto de perfil">`;
            mostrarToast('Foto de perfil actualizada');
        } catch (err) {
            mostrarToast('No se pudo actualizar la foto', true);
        }
    });
}

/* ---------- Compañeros en línea (tiempo real vía WebSocket) ---------- */
function conectarCompañerosEnLinea() {
    const contenedor = document.getElementById('listaCompañeros');
    if (!contenedor) return;

    const protocolo = location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${protocolo}://${location.host}/ws/en_linea`);

    socket.addEventListener('message', (event) => {
        try {
            const data = JSON.parse(event.data);
            pintarCompañerosEnLinea(data);
        } catch (err) {
            console.error('Error leyendo compañeros en línea:', err);
        }
    });

    socket.addEventListener('close', () => {
        // Si se cae la conexión (ej. reinicio del server), reintenta en 3s
        setTimeout(conectarCompañerosEnLinea, 3000);
    });

    socket.addEventListener('error', () => {
        socket.close();
    });
}

function pintarCompañerosEnLinea(data) {
    const contenedor = document.getElementById('listaCompañeros');
    const contador = document.getElementById('contadorEnLinea');
    if (!contenedor) return;

    if (contador) contador.textContent = data.total ?? 0;

    if (!data.conectados || data.conectados.length === 0) {
        contenedor.innerHTML = '<p class="vacio-msg">No hay compañeros conectados en este momento.</p>';
        return;
    }

    contenedor.innerHTML = data.conectados.map(u => `
        <div class="compañero-item">
            <div class="compañero-avatar">
                ${u.foto ? `<img src="${u.foto}" alt="${u.nombre}">` : `<i class="fa-solid fa-user"></i>`}
                <span class="online-dot"></span>
            </div>
            <div>
                <p class="compañero-nombre">${u.nombre}</p>
                <p class="compañero-puesto">${u.puesto || (u.tipo === 'admin' ? 'Administrador' : 'Operario')}</p>
            </div>
            <span class="compañero-hora">${u.ultima_actividad || ''}</span>
        </div>
    `).join('');
}

/* ---------- Estado del escáner del empleado actual ---------- */
async function verificarEstadoEscaner() {
    const box = document.getElementById('escanerEstadoBox');
    const titulo = document.getElementById('escanerTitulo');
    const navStatus = document.getElementById('scannerStatus');
    const navStatusText = document.getElementById('scannerStatusText');
    if (!box || !titulo) return;

    try {
        const resp = await fetch('/api/verificar_lecturas');
        const data = await resp.json();

        if (data.conectado) {
            box.classList.add('conectado');
            titulo.textContent = 'Escáner conectado';
            if (navStatus) navStatus.classList.add('connected');
            if (navStatusText) navStatusText.textContent = 'Escáner conectado';
        } else {
            box.classList.remove('conectado');
            titulo.textContent = 'Escáner no conectado';
            if (navStatus) navStatus.classList.remove('connected');
            if (navStatusText) navStatusText.textContent = 'Escáner desconectado';
        }
    } catch (err) {
        titulo.textContent = 'No se pudo verificar el escáner';
    }
}
