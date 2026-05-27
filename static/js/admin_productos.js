const formatter = new Intl.NumberFormat('es-EC', { 
    style: 'currency', currency: 'USD', minimumFractionDigits: 2 
});

document.querySelectorAll('.currency-format').forEach(el => {
    const rawValue = parseFloat(el.textContent) || 0;
    el.textContent = formatter.format(rawValue);
});

function actualizarNombreArchivo(inputId, labelId, textInputId) {
    const input = document.getElementById(inputId);
    const label = document.getElementById(labelId);
    if(input.files.length > 0) {
        label.innerHTML = `<i class="fa-solid fa-paperclip"></i> Listo: ` + input.files[0].name;
        document.getElementById(textInputId).value = '';
    }
}

// ==========================================================================
// LÓGICA DEL PANEL DE EDICIÓN FLOTANTE (DOUBLE CLICK)
// ==========================================================================
const modal = document.getElementById('editModal');
const editForm = document.getElementById('editForm');

function abrirPanelEdicion(fila) {
    // Extaer la data almacenada en los atributos data-* de la fila seleccionada
    const id = fila.getAttribute('data-id');
    const nombre = fila.getAttribute('data-nombre');
    const codigo = fila.getAttribute('data-codigo');
    const proveedor = fila.getAttribute('data-proveedor');
    const categoria = fila.getAttribute('data-categoria');
    const precio = fila.getAttribute('data-precio');
    const iva = parseFloat(fila.getAttribute('data-iva')).toFixed(1); // Normaliza el decimal (ej: "15.0")
    const stock = fila.getAttribute('data-stock');
    const imgUrl = fila.getAttribute('data-imgurl');

    // Setear la URL del action del formulario dinámicamente apuntando a tu backend de FastAPI
    editForm.action = `/admin/productos/editar/${id}`;

    // Rellenar cada campo del formulario del mini panel
    document.getElementById('edit_nombre').value = nombre;
    document.getElementById('edit_codigo').value = codigo;
    document.getElementById('edit_proveedor').value = proveedor;
    document.getElementById('edit_categoria').value = categoria;
    document.getElementById('edit_precio').value = precio;
    document.getElementById('edit_iva').value = iva;
    document.getElementById('edit_stock').value = stock;
    document.getElementById('editUrlInput').value = imgUrl;
    
    // Limpiar inputs de archivo previos
    document.getElementById('editFileInput').value = '';
    document.getElementById('editFileSelectedName').innerText = '';

    // Mostrar el panel flotante agregando la clase CSS
    modal.classList.add('open');
}

function cerrarPanelEdicion() {
    modal.classList.remove('open');
}

// Cerrar panel si el usuario da clic fuera de la tarjeta blanca
modal.addEventListener('click', (e) => {
    if (e.target === modal) cerrarPanelEdicion();
});
