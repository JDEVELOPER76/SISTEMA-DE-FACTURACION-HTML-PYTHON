// Formateador de moneda igual al archivo guía
const formatoMoneda = new Intl.NumberFormat('es-EC', { style: 'currency', currency: 'USD' });
document.querySelectorAll('.currency-format').forEach(el => {
    const valor = parseFloat(el.textContent) || 0;
    el.textContent = formatoMoneda.format(valor);
});

// Funciones básicas para control de Modales
function abrirModal(idModal) {
    document.getElementById(idModal).style.display = 'flex';
}

function cerrarModal(idModal) {
    document.getElementById(idModal).style.display = 'none';
}

// Preparar Modal de cambio de contraseña con su respectivo endpoint dinámico
function prepararPassword(username) {
    document.getElementById('usernameClaveLabel').textContent = "@" + username;
    document.getElementById('formPassword').action = `/admin/usuarios/cambiar_password/${username}`;
    abrirModal('modalPassword');
}

// Preparar Modal de eliminación segura con su respectivo endpoint dinámico
function prepararEliminar(username) {
    document.getElementById('usernameEliminarLabel').textContent = "@" + username;
    document.getElementById('formEliminar').action = `/admin/usuarios/eliminar/${username}`;
    abrirModal('modalEliminar');
}

// Cerrar modales si se hace clic fuera del recuadro blanco
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
}