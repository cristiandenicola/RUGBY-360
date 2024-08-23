# RUGBY360
brodi ho finito il setup dell'env, ti spiego cosa devi fare per usare il proj.
1. scaricati [docker](https://www.docker.com/products/docker-desktop/) <- premi.
2. una volta che te lo sei setuppato, ti cloni la repo.
3. apri un terminale nel proj e usa questo comando: docker-compose -f **path_al_docker_file** up -d.
4. aspetta che finisca di buildare le immagini e poi viene fatto partire tutto in automatico (puoi controllare su docker hub/desktop che è UP).
5. nulla, lavora.

**NB**:
- sto comando devi usarlo solo la prima volta, poi da quella successiva puoi accendere tutto da UI (aka docker desktop/hub).
- non hai bisogno di scaricare nulla, ne mosquitto ne robe strane, grazie al docker file ehehe.
- ma ti consiglio di scaricare almeno [mongo compass](https://www.mongodb.com/try/download/compass) <- premi, che è la UI con cui interfacciarti al db.

**NB2**:
- l'unico localhost che funzionerà è il 1880 (NODE-RED), quindi ti ci connetti senza prob.
- se invece vuoi testare se sono correttamente UP mongoDB e MOSQUITTO (fallo giusto la prima volta post aver buildato il container):
    - MONGO: semplicemente vai su mongo-compass e inserisci questo uri **mongodb://localhost:27017**, se ti si connette OK.
    - MOSQUITTO: apri due terminali diversi, e in entrambi scrivi **docker exec -it rugby360_mosquitto /bin/sh** (hai semplicemente creato 2 bash nel container mosquitto, senza doverlo installare su pc):
        - in uno scrivi **mosquitto_sub -h localhost -t rugby360/gps** (si mette in ascolto sul topic gps)
        - nell'altro scrivi **mosquitto_pub -h localhost -t rugby360/gps -m "Test message zzzzz"** (hai pubblicato sul topic)
        - ora torna su quello prima e controlla se hai ricevuto il mex.

**NB3**:
- teniamo come buona pratica quella di scrivere (se usate) le lib esterne nel "requirements.txt".