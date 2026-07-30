comando para correr el servidor = uvicorn server:app --host 0.0.0.0 --port 8080 --ssl-certfile=192.168.1.4+2.pem --ssl-keyfile=192.168.1.4+2-key.pem
ipconfig en cmd
obtener la ipv4 , en 192.168.1.7 colocar el ipv4

comando para crear el certificado = mkcert localhost 192.168.1.7 127.0.0.1 ::1


para el uso local es importante usar un certificado ya que no es posible habilitar la camara sin https , proximamente habra 
una app para android , quizas nativa que haga una conexion para que funcione por detras mediante una requests y asi poder usar
la camara sin certificados

obten mkcert con winget 

buscar en google como instalar mkcert con winget

--ssl-certfile=192.168.1.4+2.pem --ssl-keyfile=192.168.1.4+2-key.pem
remplaza los nombre .pem por los que que te arroja el certificado , recuerda que si el pc se apaga debes regenerar los 
certificados 

#nuva funcion para poder usar una apk para android
