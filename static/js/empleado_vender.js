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
    if (conectado && usuario) {
        statusElement.className = 'scanner-status connected';
        statusElement.innerHTML = `<i class="fa-solid fa-barcode"></i> <span>Escáner activo: ${usuario}</span>`;
        scannerConnected = true;
    } else {
        statusElement.className = 'scanner-status';
        statusElement.innerHTML = `<i class="fa-solid fa-barcode"></i> <span>Esperando escáner...</span>`;
        scannerConnected = false;
    }
}

// Escuchar productos escaneados desde el scanner
window.addEventListener('productoEscaneado', async (event) => {
    const producto = event.detail;
    
    // Verificar si es un producto válido
    if (producto && producto.id) {
        // Verificar stock
        if (producto.stock <= 0) {
            mostrarNotificacion(`⚠️ ${producto.nombre} - Producto sin stock disponible`, 'error');
            return;
        }
        
        // Agregar automáticamente al carrito
        agregarAlCarrito(producto.id, producto.nombre, producto.precio, producto.iva || 0);
        
        // Mostrar notificación visual
        mostrarNotificacion(`✅ ${producto.nombre} agregado al carrito`, 'success');
        
        // Reproducir sonido de confirmación (opcional - crear archivo beep.mp3 en static/)
        try {
            const audio = new Audio('/static/beep.mp3');
            audio.volume = 0.3;
            audio.play().catch(e => console.log('Audio no disponible'));
        } catch(e) {}
        
        // Resaltar el producto en el grid (efecto visual)
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

// Comunicación con el scanner mediante postMessage (para misma ventana/pestaña)
// También escuchar mensajes desde el scanner si está en un iframe o ventana emergente
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
        // Verificar el estado del scanner y obtener códigos pendientes
        const response = await fetch('/api/verificar_lecturas', {
            credentials: 'include',
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // Actualizar estado visual del scanner
            if (data.conectado && data.usuario) {
                actualizarEstadoScanner(true, data.usuario);
            } else {
                actualizarEstadoScanner(false);
            }
            
            // Si hay un código pendiente, procesarlo
            if (data.codigo) {
                mostrarNotificacion(`Procesando código: ${data.codigo}`, 'info');
                
                // Llamar a /api/leer_codigo para obtener detalles del producto
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
                    
                    // Verificar stock
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

// Función para abrir el scanner en una nueva ventana (opcional)
function abrirScanner() {
    const scannerWindow = window.open('/code', 'HadroxScanner', 'width=500,height=600,toolbar=no,menubar=no');
    if (scannerWindow) {
        mostrarNotificacion('🖨️ Ventana del escáner abierta. Escanea productos para agregarlos automáticamente.', 'info');
        
        // Configurar comunicación con la ventana del scanner
        scannerWindow.addEventListener('load', () => {
            // Enviar mensaje para conectar
            scannerWindow.postMessage({ type: 'CONECTAR_TERMINAL', origen: 'terminal' }, '*');
        });
        
        // Escuchar mensajes del scanner
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
        
        // Limpiar listener cuando se cierre la ventana
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

// Función original del carrito
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
        actualizarPanelTotales(0, 0, 0, 0);
        return;
    }

    let acumSubtotal0 = 0;
    let acumSubtotalIva = 0;
    let acumIva = 0;

    carrito.forEach(item => {
        const subtotalItem = item.precio_unitario * item.cantidad;
        if (item.iva > 0) {
            acumSubtotalIva += subtotalItem;
            acumIva += subtotalItem * (item.iva / 100);
        } else {
            acumSubtotal0 += subtotalItem;
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

    const totalFinal = acumSubtotal0 + acumSubtotalIva + acumIva;
    actualizarPanelTotales(acumSubtotal0, acumSubtotalIva, acumIva, totalFinal);
}

function actualizarPanelTotales(sub0, subIva, iva, total) {
    document.getElementById('subtotal-0').textContent = `$${sub0.toFixed(2)}`;
    document.getElementById('subtotal-iva').textContent = `$${subIva.toFixed(2)}`;
    document.getElementById('total-impuesto').textContent = `$${iva.toFixed(2)}`;
    document.getElementById('grand-total').textContent = `$${total.toFixed(2)}`;
}

function filtrarProductos() {
    const query = document.getElementById('search-input').value.toLowerCase().trim();
    document.querySelectorAll('.product-card').forEach(card => {
        const nombre = card.getAttribute('data-nombre') || '';
        card.style.display = nombre.includes(query) ? 'flex' : 'none';
    });
}

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
        cliente_id: parseInt(document.getElementById('cliente-select').value),
        metodo_pago: document.getElementById('pago-select').value,
        detalles: carrito
    };

    // Deshabilitar botón durante el proceso
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

// Agregar botón flotante para abrir scanner (opcional)
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
    `;
    btnScanner.onmouseover = () => btnScanner.style.transform = 'translateY(-2px)';
    btnScanner.onmouseout = () => btnScanner.style.transform = 'translateY(0)';
    btnScanner.onclick = abrirScanner;
    document.body.appendChild(btnScanner);
}

// Verificar scanner periódicamente (cada 5 segundos para no saturar el servidor)
setInterval(verificarScannerActivo, 5000);

// Funciones para el modal de confirmación
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

// Cerrar modal al hacer clic fuera
document.addEventListener('DOMContentLoaded', function() {
    const modalOverlay = document.getElementById('modal-overlay');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', function(e) {
            if (e.target === modalOverlay) {
                cerrarModal();
            }
        });
    }
});

// Inicializar
verificarScannerActivo();
agregarBotonScannerFlotante();