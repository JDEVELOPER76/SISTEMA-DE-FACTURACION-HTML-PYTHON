let ultimoCodigoScaneado = "";
let lockEscaneo = false;
let html5QrcodeScanner = null;
let currentSessionUser = null;

// Manejar login
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    const loginBtn = document.querySelector('#loginForm .btn-login');
    const originalText = loginBtn.innerHTML;
    loginBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Validando...';
    loginBtn.disabled = true;
    
    try {
        const response = await fetch('/api/scanner_login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            // Login exitoso
            currentSessionUser = username;
            localStorage.setItem('scanner_session', JSON.stringify({
                username: username,
                session_id: data.session_id,
                timestamp: Date.now()
            }));
            
            document.getElementById('loginSection').style.display = 'none';
            document.getElementById('scannerSection').style.display = 'block';
            document.getElementById('currentUser').textContent = username;
            
            // Inicializar scanner
            inicializarEscaner();
            actualizarStatusConectado(true);
        } else {
            // Error de login
            document.getElementById('loginError').classList.remove('hidden');
            document.getElementById('errorMessage').textContent = data.detail || 'Credenciales incorrectas';
            setTimeout(() => {
                document.getElementById('loginError').classList.add('hidden');
            }, 3000);
        }
    } catch (error) {
        document.getElementById('loginError').classList.remove('hidden');
        document.getElementById('errorMessage').textContent = 'Error de conexión con el servidor';
        setTimeout(() => {
            document.getElementById('loginError').classList.add('hidden');
        }, 3000);
    } finally {
        loginBtn.innerHTML = originalText;
        loginBtn.disabled = false;
    }
});

// Cerrar sesión
document.getElementById('logoutBtn')?.addEventListener('click', async () => {
    if (currentSessionUser) {
        try {
            await fetch('/api/scanner_logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username: currentSessionUser })
            });
        } catch (error) {
            console.error('Error en logout:', error);
        }
    }
    
    localStorage.removeItem('scanner_session');
    currentSessionUser = null;
    
    if (html5QrcodeScanner) {
        await html5QrcodeScanner.clear();
        html5QrcodeScanner = null;
    }
    
    document.getElementById('scannerSection').style.display = 'none';
    document.getElementById('loginSection').style.display = 'block';
    document.getElementById('loginForm').reset();
    document.getElementById('username').focus();
});

// Verificar sesión guardada
async function verificarSesionGuardada() {
    const savedSession = localStorage.getItem('scanner_session');
    if (savedSession) {
        try {
            const session = JSON.parse(savedSession);
            const timeElapsed = Date.now() - session.timestamp;
            const SESSION_TIMEOUT = 8 * 60 * 60 * 1000; // 8 horas
            
            if (timeElapsed < SESSION_TIMEOUT) {
                // Validar sesión con el servidor
                const response = await fetch('/api/scanner_verify', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ 
                        username: session.username, 
                        session_id: session.session_id 
                    })
                });
                
                const data = await response.json();
                
                if (response.ok && data.valid) {
                    currentSessionUser = session.username;
                    document.getElementById('loginSection').style.display = 'none';
                    document.getElementById('scannerSection').style.display = 'block';
                    document.getElementById('currentUser').textContent = session.username;
                    inicializarEscaner();
                    actualizarStatusConectado(true);
                    return;
                }
            }
        } catch (error) {
            console.error('Error verificando sesión:', error);
        }
    }
    // No hay sesión válida, mostrar login
    localStorage.removeItem('scanner_session');
}

function actualizarStatusConectado(conectado) {
    const statusBadge = document.getElementById('status');
    if (conectado) {
        statusBadge.innerHTML = '<i class="fa-solid fa-circle-check"></i> Conectado a: ' + currentSessionUser;
        statusBadge.className = "status-badge status-success";
    } else {
        statusBadge.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> Sin conexión';
        statusBadge.className = "status-badge";
    }
}

function onScanSuccess(decodedText, decodedResult) {
    if (decodedText === ultimoCodigoScaneado || lockEscaneo || !currentSessionUser) {
        return;
    }
    
    lockEscaneo = true;
    ultimoCodigoScaneado = decodedText;
    
    // Reproducir sonido beep
    const beepSound = document.getElementById('beepSound');
    if (beepSound) {
        beepSound.play().catch(error => console.log('Error reproduciendo sonido:', error));
    }
    
    document.getElementById('result-text').innerHTML = `
        <span style="color: var(--hadrox-navy);">📌 Código Detectado: </span>
        <strong style="color: var(--hadrox-blue); font-size: 16px;">${decodedText}</strong>
        <i class="fa-solid fa-spinner fa-spin"></i>
    `;
    
    enviarAlLocalhost(decodedText);
}

async function enviarAlLocalhost(codigo, esDesdeArchivo = false) {
    const statusBadge = document.getElementById('status');
    try {
        // Enviar el código a /api/transmitir_escaneo (la terminal de ventas lo procesará)
        const response = await fetch('/api/transmitir_escaneo', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                codigo_barras: codigo,
                username: currentSessionUser
            })
        });
        
        if (response.ok) {
            document.getElementById('result-text').innerHTML = `
                <span style="color: var(--hadrox-navy);">📤 Código transmitido: </span>
                <strong style="color: var(--hadrox-blue);">${codigo}</strong>
            `;
            statusBadge.innerHTML = `<i class="fa-solid fa-circle-check"></i> Transmitiendo...`;
            statusBadge.className = "status-badge status-success";
            
            // SI fue desde archivo, limpiar después de éxito
            if (esDesdeArchivo) {
                setTimeout(() => {
                    document.getElementById('fotoInput').value = ''; // Limpiar el input
                    lockEscaneo = false;
                    document.getElementById('result-text').innerHTML = `<span style="color: #94a3b8;">Esperando lectura...</span>`;
                }, 2000);
            }
            
        } else {
            const error = await response.json();
            document.getElementById('result-text').innerHTML = `
                <span style="color: var(--hadrox-red);">❌ Error: </span>
                <span>${error.detail || 'Error en la transmisión'}</span>
            `;
            statusBadge.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> Error de transmisión`;
            statusBadge.className = "status-badge status-error";
            
            // Limpiar lock si fue desde archivo
            if (esDesdeArchivo) {
                setTimeout(() => {
                    lockEscaneo = false;
                }, 2000);
            }
        }
    } catch (error) {
        document.getElementById('result-text').innerHTML = `
            <span style="color: var(--hadrox-red);">⚠️ Error de conexión</span>
        `;
        statusBadge.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> Error de comunicación`;
        statusBadge.className = "status-badge status-error";
        console.error("Error transmitiendo datos:", error);
        
        // Limpiar lock si fue desde archivo
        if (esDesdeArchivo) {
            setTimeout(() => {
                lockEscaneo = false;
            }, 2000);
        }
    } finally {
        // Solo limpiar timer si fue desde CÁMARA (no desde archivo)
        if (!esDesdeArchivo) {
            setTimeout(() => {
                lockEscaneo = false;
                ultimoCodigoScaneado = ""; // Limpiar para permitir re-escanear el mismo código
                setTimeout(() => {
                    document.getElementById('result-text').innerHTML = `<span style="color: #94a3b8;">Esperando lectura...</span>`;
                }, 1500);
            }, 1000);
        }
    }
}        
function inicializarEscaner() {
    if (html5QrcodeScanner) {
        html5QrcodeScanner.clear();
    }
    
    const readerElement = document.getElementById('reader');
    readerElement.style.display = 'block';
    
    html5QrcodeScanner = new Html5QrcodeScanner(
        "reader", 
        { 
            fps: 15, 
            qrbox: { width: 300, height: 150 },
            aspectRatio: 1.777778
        },
        false
    );
    html5QrcodeScanner.render(onScanSuccess);
}

// Manejar carga de imágenes desde archivo
document.getElementById('fotoInput')?.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file || lockEscaneo || !currentSessionUser) return;

    lockEscaneo = true;
    document.getElementById('result-text').innerHTML = `
        <span style="color: var(--hadrox-navy);">📸 Procesando imagen...</span>
        <i class="fa-solid fa-spinner fa-spin"></i>
    `;

    try {
        // Leer la imagen como URL
        const reader = new FileReader();
        reader.onload = async (event) => {
            const imageUrl = event.target.result;
            
            // Usar html5-qrcode para decodificar la imagen
            try {
                const decodedText = await Html5Qrcode.scanImageFile(imageUrl);
                
                document.getElementById('result-text').innerHTML = `
                    <span style="color: var(--hadrox-navy);">📌 Código detectado: </span>
                    <strong style="color: var(--hadrox-blue); font-size: 16px;">${decodedText}</strong>
                    <i class="fa-solid fa-spinner fa-spin"></i>
                `;
                
                // Enviar con flag esDesdeArchivo = true
                await enviarAlLocalhost(decodedText, true);
                
            } catch (error) {
                document.getElementById('result-text').innerHTML = `
                    <span style="color: var(--hadrox-red);">❌ No se detectó código en la imagen</span>
                `;
                lockEscaneo = false;
            }
        };
        reader.readAsDataURL(file);
        
    } catch (error) {
        document.getElementById('result-text').innerHTML = `
            <span style="color: var(--hadrox-red);">⚠️ Error procesando imagen</span>
        `;
        lockEscaneo = false;
        console.error("Error procesando imagen:", error);
    }
});

// Iniciar al cargar la página
window.addEventListener('DOMContentLoaded', verificarSesionGuardada);
