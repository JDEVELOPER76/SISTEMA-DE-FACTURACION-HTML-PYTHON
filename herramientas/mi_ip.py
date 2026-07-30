import socket



def obtener_ip_local():
    """Obtiene la dirección IP local de la máquina."""
    try:
        # Crear un socket UDP y conectarse a un servidor externo para obtener la IP local
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        print(f"Error al obtener la IP local: {e}")
        return None

