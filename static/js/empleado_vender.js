let carrito = [];
let scannerConnected = false;

// Función para mostrar notificaciones
function mostrarNotificacion(mensaje, tipo = 'success') {
    const notificacion = document.createElement('div');
    notificacion.className = `notification ${tipo}`;
    const icono = tipo === 'success' ? 'fa-check-circle' : (tipo === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle');
    notificacion.innerHTML = `<i class="fa-solid ${icono}"></i> ${mensaje}`;
    document.body.appendChild(notificacion);
    
    setTimeout(() => {
        notificacion.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notificacion.remove(), 300);
    }, 3000);
}

// Actualizar estado del scanner en la UI
function actualizarEstadoScanner(conectado, usuario = null) {
    const statusElement = document.getElementById('scannerStatus');
    const statusText = document.getElementById('scannerStatusText');
    if (conectado && usuario) {
        statusElement.className = 'scanner-status connected';
        statusText.textContent = `Escáner activo: ${usuario}`;
        scannerConnected = true;
    } else {
        statusElement.className = 'scanner-status';
        statusText.textContent = 'Esperando escáner...';
        scannerConnected = false;
    }
}

// Escuchar productos escaneados desde el scanner
window.addEventListener('productoEscaneado', async (event) => {
    const producto = event.detail;
    
    if (producto && producto.id) {
        if (producto.stock <= 0) {
            mostrarNotificacion(`⚠️ ${producto.nombre} - Producto sin stock disponible`, 'error');
            return;
        }
        agregarAlCarrito(producto.id, producto.nombre, producto.precio, producto.iva || 0);
        mostrarNotificacion(`✅ ${producto.nombre} agregado al carrito`, 'success');
        
        try {
            const audio = new Audio('/static/beep.mp3');
            audio.volume = 0.3;
            audio.play().catch(e => console.log('Audio no disponible'));
        } catch(e) {}
        
        const productCard = document.querySelector(`.product-card[data-id="${producto.id}"]`);
        if (productCard) {
            productCard.style.transition = 'box-shadow 0.2s';
            productCard.style.boxShadow = '0 0 0 2px var(--hadrox-success)';
            setTimeout(() => {
                productCard.style.boxShadow = '';
            }, 500);
        }
    }
});

window.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'PRODUCTO_ESCANEADO') {
        const producto = event.data.producto;
        if (producto && producto.id) {
            agregarAlCarrito(producto.id, producto.nombre, producto.precio, producto.iva || 0);
            mostrarNotificacion(`✅ ${producto.nombre} agregado (Scanner)`, 'success');
        }
    }
});

// Verificar si hay un scanner activo y procesar códigos escaneados
async function verificarScannerActivo() {
    try {
        const response = await fetch('/api/verificar_lecturas', {
            credentials: 'include',
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (response.ok) {
            const data = await response.json();
            
            if (data.conectado && data.usuario) {
                actualizarEstadoScanner(true, data.usuario);
            } else {
                actualizarEstadoScanner(false);
            }
            
            if (data.codigo) {
                mostrarNotificacion(`Procesando código: ${data.codigo}`, 'info');
                
                const productoResponse = await fetch('/api/leer_codigo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        codigo_barras: data.codigo,
                        usuario: data.usuario 
                    })
                });
                
                if (productoResponse.ok) {
                    const producto = await productoResponse.json();
                    
                    if (producto.stock > 0) {
                        agregarAlCarrito(producto.id, producto.nombre, producto.precio, producto.iva || 0);
                        mostrarNotificacion(`✅ ${producto.nombre} agregado al carrito`, 'success');
                    } else {
                        mostrarNotificacion(`⚠️ ${producto.nombre} - Sin stock disponible`, 'error');
                    }
                } else {
                    const error = await productoResponse.json();
                    mostrarNotificacion(`❌ ${error.detail || 'Código no reconocido'}`, 'error');
                }
            }
        }
    } catch (error) {
        actualizarEstadoScanner(false);
    }
}

// Función para abrir el scanner en una nueva ventana
function abrirScanner() {
    const scannerWindow = window.open('/code', 'HadroxScanner', 'width=500,height=600,toolbar=no,menubar=no');
    if (scannerWindow) {
        mostrarNotificacion('🖨️ Ventana del escáner abierta. Escanea productos para agregarlos automáticamente.', 'info');
        
        scannerWindow.addEventListener('load', () => {
            scannerWindow.postMessage({ type: 'CONECTAR_TERMINAL', origen: 'terminal' }, '*');
        });
        
        const messageHandler = (event) => {
            if (event.data && event.data.type === 'PRODUCTO_ESCANEADO') {
                const producto = event.data.producto;
                if (producto && producto.id) {
                    agregarAlCarrito(producto.id, producto.nombre, producto.precio, producto.iva || 0);
                    mostrarNotificacion(`✅ ${producto.nombre} agregado (Scanner)`, 'success');
                }
            }
        };
        window.addEventListener('message', messageHandler);
        
        const checkClosed = setInterval(() => {
            if (scannerWindow.closed) {
                clearInterval(checkClosed);
                window.removeEventListener('message', messageHandler);
                mostrarNotificacion('🔌 Ventana del escáner cerrada', 'info');
                actualizarEstadoScanner(false);
            }
        }, 1000);
    } else {
        mostrarNotificacion('⚠️ No se pudo abrir el escáner. Permite ventanas emergentes.', 'error');
    }
}

// ==========================================
//   FUNCIONES DEL CARRITO
// ==========================================

function agregarAlCarrito(id, nombre, precio, iva) {
    const itemExistente = carrito.find(item => item.producto_id === id);
    if (itemExistente) {
        itemExistente.cantidad += 1;
    } else {
        carrito.push({
            producto_id: id,
            nombre: nombre,
            precio_unitario: parseFloat(precio),
            cantidad: 1,
            iva: parseFloat(iva)
        });
    }
    renderizarCarrito();
}

function removerDelCarrito(id) {
    carrito = carrito.filter(item => item.producto_id !== id);
    renderizarCarrito();
}

function renderizarCarrito() {
    const container = document.getElementById('cart-container');
    container.innerHTML = '';

    if (carrito.length === 0) {
        container.innerHTML = `<p style="text-align:center; color: var(--hadrox-light); font-size:13px; margin-top:40px; font-weight:500;">El carrito de compras está vacío.</p>`;
        actualizarPanelTotales(0);
        document.getElementById('cart-count').textContent = '0';
        return;
    }

    let totalFinal = 0;

    carrito.forEach(item => {
        const subtotalItem = item.precio_unitario * item.cantidad;
        if (item.iva > 0) {
            totalFinal += subtotalItem + (subtotalItem * (item.iva / 100));
        } else {
            totalFinal += subtotalItem;
        }

        const itemDiv = document.createElement('div');
        itemDiv.className = 'cart-item';
        itemDiv.innerHTML = `
            <div class="item-details">
                <h5>${item.nombre}</h5>
                <p>$${item.precio_unitario.toFixed(2)} c/u ${item.iva > 0 ? `<small style="color:var(--hadrox-blue); font-weight:bold;">(IVA ${item.iva}%)</small>` : ''}</p>
            </div>
            <div class="item-controls">
                <span class="quantity-badge">x${item.cantidad}</span>
                <button class="btn-remove" onclick="removerDelCarrito(${item.producto_id})">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </div>
        `;
        container.appendChild(itemDiv);
    });

    actualizarPanelTotales(totalFinal);
    document.getElementById('cart-count').textContent = carrito.reduce((sum, item) => sum + item.cantidad, 0);
}

function actualizarPanelTotales(total) {
    document.getElementById('grand-total').textContent = `$${total.toFixed(2)}`;
}

function filtrarProductos() {
    const query = document.getElementById('search-input').value.toLowerCase().trim();
    document.querySelectorAll('.product-card').forEach(card => {
        const nombre = card.getAttribute('data-nombre') || '';
        card.style.display = nombre.includes(query) ? 'flex' : 'none';
    });
}

// ==========================================
//   FUNCIONES DE VENTA
// ==========================================

function confirmarVenta() {
    if (carrito.length === 0) {
        mostrarNotificacion('Por favor, añada por lo menos un artículo al carrito.', 'error');
        return;
    }

    const totalElement = document.getElementById('grand-total');
    const totalAmount = totalElement.textContent;
    const metodoPago = document.getElementById('pago-select').value;
    const clienteSelect = document.getElementById('cliente-select');
    const clienteText = clienteSelect.options[clienteSelect.selectedIndex].text;

    mostrarModalConfirmacion(totalAmount, metodoPago, clienteText);
}

async function procesarVenta() {
    if (carrito.length === 0) {
        mostrarNotificacion('Por favor, añada por lo menos un artículo al carrito.', 'error');
        return;
    }
    
    const payload = {
        cliente_id: parseInt(document.getElementById('cliente-select').value) || null,
        metodo_pago: document.getElementById('pago-select').value,
        detalles: carrito
    };

    const btnCheckout = document.querySelector('.btn-checkout');
    const originalText = btnCheckout.innerHTML;
    btnCheckout.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Procesando...';
    btnCheckout.disabled = true;

    try {
        const response = await fetch('/api/vender', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const result = await response.json();
            mostrarNotificacion(`🎉 ¡Venta #${result.venta_id} registrada correctamente!`, 'success');
            carrito = []; 
            renderizarCarrito(); 
        } else {
            const errorResponse = await response.json();
            mostrarNotificacion('Error en cobro: ' + (errorResponse.detail || 'No se pudo procesar.'), 'error');
        }
    } catch (err) {
        mostrarNotificacion('Error de conexión con el backend Hadrox Server.', 'error');
    } finally {
        btnCheckout.innerHTML = originalText;
        btnCheckout.disabled = false;
    }
}

// ==========================================
//   MODALES
// ==========================================

function mostrarModalConfirmacion(total, metodo, cliente) {
    document.getElementById('modal-total').textContent = total;
    document.getElementById('modal-metodo').textContent = metodo;
    document.getElementById('modal-cliente').textContent = cliente;
    document.getElementById('modal-overlay').classList.add('active');
}

function cerrarModal() {
    document.getElementById('modal-overlay').classList.remove('active');
}

function confirmarOperacion() {
    cerrarModal();
    procesarVenta();
}

// ==========================================
//   MANEJO DEL MODAL DE CLIENTE
// ==========================================

const modalCliente = document.getElementById('modalCliente');
const btnAgregarCliente = document.getElementById('btnAgregarCliente');
const btnCancelarCliente = document.getElementById('cancelarCliente');
const cerrarModalCliente = document.getElementById('cerrarModalCliente');
const formNuevoCliente = document.getElementById('formNuevoCliente');

function abrirModalCliente() {
    modalCliente.classList.add('active');
    setTimeout(() => {
        document.getElementById('inputClienteNombre').focus();
    }, 100);
}

function cerrarModalClienteFn() {
    modalCliente.classList.remove('active');
    formNuevoCliente.reset();
    // Resetear el botón guardar a su estado original
    const btnGuardar = document.getElementById('btnGuardarCliente');
    btnGuardar.innerHTML = '<i class="fa-solid fa-check"></i> Guardar Cliente';
    btnGuardar.disabled = false;
}

if (btnAgregarCliente) {
    btnAgregarCliente.addEventListener('click', abrirModalCliente);
}

if (btnCancelarCliente) {
    btnCancelarCliente.addEventListener('click', cerrarModalClienteFn);
}

if (cerrarModalCliente) {
    cerrarModalCliente.addEventListener('click', cerrarModalClienteFn);
}

modalCliente.addEventListener('click', (e) => {
    if (e.target === modalCliente) {
        cerrarModalClienteFn();
    }
});

// Procesar formulario de nuevo cliente
formNuevoCliente.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const nombre = document.getElementById('inputClienteNombre').value.trim();
    const tipo_identificacion = document.getElementById('inputClienteTipoID').value;
    const identificacion = document.getElementById('inputClienteID').value.trim();
    const telefono = document.getElementById('inputClienteTelefono').value.trim();
    const email = document.getElementById('inputClienteEmail').value.trim();
    const direccion = document.getElementById('inputClienteDireccion').value.trim();
    
    if (!nombre) {
        mostrarNotificacion('Por favor ingresa el nombre del cliente', 'error');
        document.getElementById('inputClienteNombre').focus();
        return;
    }
    
    const btnGuardar = document.getElementById('btnGuardarCliente');
    const textoOriginal = btnGuardar.innerHTML;
    btnGuardar.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Guardando...';
    btnGuardar.disabled = true;
    
    try {
        const response = await fetch('/api/clientes/rapido', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nombre,
                tipo_identificacion,
                identificacion: identificacion || null,
                telefono: telefono || null,
                email: email || null,
                direccion: direccion || null
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const select = document.getElementById('cliente-select');
            const option = document.createElement('option');
            option.value = data.cliente.id;
            const displayText = data.cliente.identificacion ? 
                `${data.cliente.nombre} (${data.cliente.identificacion})` : 
                data.cliente.nombre;
            option.textContent = displayText;
            // Guardar los datos completos en el atributo data-detalle
            option.dataset.detalle = JSON.stringify(data.cliente);
            select.appendChild(option);
            select.value = data.cliente.id;
            
            // Actualizar el detalle del cliente
            actualizarDetalleCliente(data.cliente);
            
            mostrarNotificacion(`✅ Cliente "${data.cliente.nombre}" agregado exitosamente`, 'success');
            cerrarModalClienteFn();
        } else {
            mostrarNotificacion(data.detail || 'Error al agregar cliente', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        mostrarNotificacion('Error de conexión al servidor', 'error');
    } finally {
        btnGuardar.innerHTML = textoOriginal;
        btnGuardar.disabled = false;
    }
});

// ==========================================
//   DETALLE DEL CLIENTE SELECCIONADO
// ==========================================

const clienteSelect = document.getElementById('cliente-select');
const clienteDetalle = document.getElementById('clienteDetalle');

function actualizarDetalleCliente(cliente) {
    if (!cliente || !cliente.id) {
        clienteDetalle.style.display = 'none';
        return;
    }
    
    document.getElementById('clienteDetalleNombre').textContent = cliente.nombre || '-';
    document.getElementById('clienteDetalleID').textContent = cliente.identificacion || 'No registrada';
    document.getElementById('clienteDetalleTelefono').textContent = cliente.telefono || 'No registrado';
    document.getElementById('clienteDetalleDireccion').textContent = cliente.direccion || 'No registrada';
    document.getElementById('clienteDetalleEmail').textContent = cliente.email || 'No registrado';
    clienteDetalle.style.display = 'block';
}

if (clienteSelect) {
    clienteSelect.addEventListener('change', function(e) {
        const selectedOption = this.options[this.selectedIndex];
        
        if (!this.value) {
            clienteDetalle.style.display = 'none';
            return;
        }
        
        // Intentar cargar desde data-detalle
        if (selectedOption.dataset.detalle) {
            try {
                const detalle = JSON.parse(selectedOption.dataset.detalle);
                actualizarDetalleCliente(detalle);
                return;
            } catch (e) {
                console.warn('Error al parsear detalle del cliente:', e);
            }
        }
        
        // Si no hay detalle en el option, hacer fetch
        fetch(`/api/clientes/${this.value}`)
            .then(res => {
                if (!res.ok) throw new Error('Cliente no encontrado');
                return res.json();
            })
            .then(data => {
                if (data) {
                    actualizarDetalleCliente(data);
                    // Guardar en el option para caché
                    selectedOption.dataset.detalle = JSON.stringify(data);
                }
            })
            .catch(error => {
                console.error('Error al cargar detalles del cliente:', error);
                clienteDetalle.style.display = 'none';
            });
    });
    
    // Si hay un cliente seleccionado por defecto, mostrar sus detalles
    if (clienteSelect.value) {
        clienteSelect.dispatchEvent(new Event('change'));
    }
}

// ==========================================
//   BUSCADOR RÁPIDO DE CLIENTES
// ==========================================

let timeoutBusqueda;
const busquedaCliente = document.getElementById('busquedaCliente');
const resultadosBusqueda = document.getElementById('resultadosBusqueda');

if (busquedaCliente) {
    busquedaCliente.addEventListener('input', (e) => {
        clearTimeout(timeoutBusqueda);
        const termino = e.target.value.trim();
        
        if (termino.length < 2) {
            resultadosBusqueda.style.display = 'none';
            return;
        }
        
        timeoutBusqueda = setTimeout(async () => {
            try {
                const response = await fetch(`/api/clientes/buscar?termino=${encodeURIComponent(termino)}`);
                const data = await response.json();
                
                if (data.clientes && data.clientes.length > 0) {
                    resultadosBusqueda.style.display = 'block';
                    resultadosBusqueda.innerHTML = data.clientes.map(cliente => `
                        <div class="resultado-cliente" data-id="${cliente.id}" 
                             style="padding: 10px 14px; border-bottom: 1px solid var(--hadrox-border); cursor: pointer; transition: background 0.2s;">
                            <div style="font-weight: 600; color: var(--hadrox-navy);">${cliente.nombre}</div>
                            <div style="font-size: 12px; color: var(--hadrox-light);">
                                ${cliente.identificacion ? `${cliente.tipo_identificacion || 'ID'}: ${cliente.identificacion}` : 'Sin identificación'}
                                ${cliente.telefono ? `· 📞 ${cliente.telefono}` : ''}
                            </div>
                        </div>
                    `).join('');
                    
                    resultadosBusqueda.querySelectorAll('.resultado-cliente').forEach(el => {
                        el.addEventListener('click', function() {
                            const id = parseInt(this.dataset.id);
                            const select = document.getElementById('cliente-select');
                            
                            // Buscar la opción con el ID
                            for (let option of select.options) {
                                if (parseInt(option.value) === id) {
                                    select.value = id;
                                    break;
                                }
                            }
                            
                            busquedaCliente.value = '';
                            resultadosBusqueda.style.display = 'none';
                            select.dispatchEvent(new Event('change'));
                        });
                    });
                } else {
                    resultadosBusqueda.style.display = 'none';
                }
            } catch (error) {
                console.error('Error en búsqueda de clientes:', error);
                resultadosBusqueda.style.display = 'none';
            }
        }, 300);
    });
    
    // Ocultar resultados al perder el foco
    busquedaCliente.addEventListener('blur', () => {
        setTimeout(() => {
            resultadosBusqueda.style.display = 'none';
        }, 300);
    });
}

// ==========================================
//   BOTÓN FLOTANTE DEL ESCÁNER
// ==========================================

function agregarBotonScannerFlotante() {
    const btnScanner = document.createElement('button');
    btnScanner.innerHTML = '<i class="fa-solid fa-barcode"></i> Escáner';
    btnScanner.style.cssText = `
        position: fixed;
        bottom: 20px;
        left: 20px;
        background: var(--hadrox-navy);
        color: white;
        border: none;
        padding: 12px 18px;
        border-radius: 50px;
        font-weight: 600;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 8px;
        z-index: 100;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transition: all 0.2s;
        font-size: 13px;
    `;
    btnScanner.onmouseover = () => btnScanner.style.transform = 'translateY(-2px)';
    btnScanner.onmouseout = () => btnScanner.style.transform = 'translateY(0)';
    btnScanner.onclick = abrirScanner;
    document.body.appendChild(btnScanner);
}

// ==========================================
//   INICIALIZACIÓN
// ==========================================

// Cerrar modal de confirmación al hacer clic fuera
document.addEventListener('DOMContentLoaded', function() {
    const modalOverlay = document.getElementById('modal-overlay');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', function(e) {
            if (e.target === modalOverlay) {
                cerrarModal();
            }
        });
    }
    
    // Verificar scanner cada 5 segundos
    setInterval(verificarScannerActivo, 5000);
    verificarScannerActivo();
    agregarBotonScannerFlotante();
});