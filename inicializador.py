import multiprocessing
import os

import uvicorn

from register import registro as registro_app
from server import app as server_app
from herramientas.mi_ip import obtener_ip_local

def run_server() -> None:
    uvicorn.run(app=server_app, host="0.0.0.0", port=8000, log_level="info")


def run_register() -> None:
    uvicorn.run(app=registro_app, port=8001, log_level="info")


def main() -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")

    print("Servidor iniciado en http://localhost:8000")
    print(f"Puedes visitar el servidor en http://{obtener_ip_local()}:8000")
    print("-" * 40)
    print("Si no existe un usuario usa el registro para iniciar con un usuario administrador.")
    print("Registro iniciado en http://localhost:8001")
    print("-" * 40)

    procesos = [
        multiprocessing.Process(target=run_server, name="server", daemon=True),
        multiprocessing.Process(target=run_register, name="register", daemon=True),
    ]

    for proceso in procesos:
        proceso.start()

    try:
        for proceso in procesos:
            proceso.join()
    except KeyboardInterrupt:
        print("Deteniendo servidores...")
        for proceso in procesos:
            if proceso.is_alive():
                proceso.terminate()
                proceso.join(timeout=5)
                if proceso.is_alive():
                    proceso.kill()
                    proceso.join()


if __name__ == "__main__":
    main()