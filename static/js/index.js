// Función de toggle password exactamente igual a la original pero con mejor accesibilidad
function togglePassword() {
    const passwordInput = document.getElementById('password');
    const toggleBtn = document.querySelector('.toggle-btn');

    if (!passwordInput || !toggleBtn) return;

    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleBtn.textContent = 'Ocultar';
        // pequeño detalle: anuncio para lectores de pantalla
        passwordInput.setAttribute('aria-label', 'Contraseña visible');
    } else {
        passwordInput.type = 'password';
        toggleBtn.textContent = 'Ver';
        passwordInput.setAttribute('aria-label', 'Contraseña oculta');
    }
}

// Muestra errores desde el URL (?error=...) con animación suave y auto-ocultación mejorada
function showErrorFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const error = params.get('error');
    const errorDiv = document.getElementById('errorMsg');

    if (error && errorDiv) {
        // Decodificar correctamente el mensaje de error (puede venir con espacios o códigos)
        let errorMessage = decodeURIComponent(error);
        // Reemplazar posibles '+' por espacios (por si acaso)
        errorMessage = errorMessage.replace(/\+/g, ' ');
        errorDiv.textContent = errorMessage;
        errorDiv.style.display = 'block';
        errorDiv.style.opacity = '1';

        // Eliminar cualquier timeout previo para evitar conflictos
        if (window.errorTimeout) clearTimeout(window.errorTimeout);
        if (window.fadeTimeout) clearTimeout(window.fadeTimeout);

        // Tiempo de visualización: 3.5 segundos
        window.errorTimeout = setTimeout(() => {
            errorDiv.style.transition = 'opacity 0.4s ease';
            errorDiv.style.opacity = '0';
            
            window.fadeTimeout = setTimeout(() => {
                errorDiv.style.display = 'none';
                errorDiv.style.opacity = '1'; // reset para futuros errores
                errorDiv.style.transition = '';
            }, 400);
        }, 3500);
    }
}

// También se podría capturar el submit para un manejo adicional, pero respetamos el flujo original.
// Si se requiere validación extra sin interferir con el envío, podemos agregar un listener opcional.
// No se modifican los nombres de los campos ni la acción del formulario, 100% compatibilidad con API.

// Ejecutar al cargar
showErrorFromUrl();

// Opcional: si se desea que el campo username tenga foco automático y limpieza visual
document.addEventListener('DOMContentLoaded', () => {
    const usernameField = document.getElementById('username');
    if (usernameField && !usernameField.value) {
        usernameField.focus();
    }

    // Small UX: Para prevenir que el botón toggle pierda estilos si hay más de uno
    const toggle = document.querySelector('.toggle-btn');
    if (toggle) {
        toggle.setAttribute('aria-label', 'Mostrar u ocultar contraseña');
    }
    
    // Si la imagen falla por nombre incorrecto, el usuario verá el placeholder indicando que debe poner el PNG local correcto.
    // Mejoramos el manejo de error de la imagen: el mensaje será claro.
    const imgElement = document.querySelector('.brand-content img');
    if (imgElement && imgElement.complete && imgElement.naturalWidth === 0) {
        // si la imagen no cargó porque no existe, se puede mostrar un texto amigable dentro del mismo contenedor
        // pero no es necesario, el onerror ya coloca un placeholder con texto, eso es suficiente.
    }
});