#!/bin/bash
set -e

# Funktion zum Überprüfen, ob Docker läuft
check_docker() {
    if ! command -v docker &>/dev/null; then
        echo "🚨 Docker ist nicht installiert. Bitte installiere Docker und versuche es erneut."
        exit 1
    fi

    if ! docker info &>/dev/null; then
        echo "🚨 Docker Engine läuft nicht. Stelle sicher, dass Docker läuft."
        exit 1
    fi
}

# Überprüfe, ob Docker läuft
echo "🔍 Überprüfe Docker..."
check_docker

# Zielverzeichnisse und Dateien, die berücksichtigt werden sollen
TARGETS=(
  "app"
  "frontend"
  "docker-compose.yml"
  "Dockerfile"
)

# Muster für zu ignorierende Dateien/Ordner (z.B. node_modules, __pycache__)
IGNORE_PATTERN="*/node_modules/*"

# Pfade für die Checksum-Dateien
OLD_CHECKSUM_FILE="./deploy-checksums.txt"
NEW_CHECKSUM_FILE="./deploy-checksums-new.txt"

echo "Berechne Checksums für alle relevanten Dateien ..."
# Berechne die Checksum für jedes Zielverzeichnis, ignoriere bestimmte Muster
CHECKSUMS=()
for TARGET in "${TARGETS[@]}"; do
    if [ -d "$TARGET" ] || [ -f "$TARGET" ]; then
        CHECKSUM=$(find "$TARGET" -type f ! -path "*/node_modules/*" ! -path "*/__pycache__/*" ! -path "*/.git/*" -exec md5sum {} + | md5sum | awk '{print $1}')
        CHECKSUMS+=("$TARGET:$CHECKSUM")
    fi
done

# Speichere die neuen Checksums
printf "%s\n" "${CHECKSUMS[@]}" > "$NEW_CHECKSUM_FILE"

# Falls es eine alte Checksum-Datei gibt, vergleiche sie mit der neuen
if [ -f "$OLD_CHECKSUM_FILE" ]; then
    CHANGED_SERVICES=()
    
    while IFS= read -r line; do
        TARGET=$(echo "$line" | cut -d':' -f1)
        OLD_HASH=$(echo "$line" | cut -d':' -f2)
        NEW_HASH=$(grep "^$TARGET:" "$NEW_CHECKSUM_FILE" | cut -d':' -f2)

        if [ "$OLD_HASH" != "$NEW_HASH" ]; then
            echo "🔄 Änderungen in $TARGET erkannt!"
            CHANGED_SERVICES+=("$TARGET")
        fi
    done < "$OLD_CHECKSUM_FILE"

    if [ ${#CHANGED_SERVICES[@]} -eq 0 ]; then
        echo "✅ Keine Änderungen festgestellt. Build & Push übersprungen."
    else
        # Speichere die neue Checksum-Datei als Basis für den nächsten Vergleich
        cp "$NEW_CHECKSUM_FILE" "$OLD_CHECKSUM_FILE"

        # Build und Push nur für geänderte Services
        for SERVICE in "${CHANGED_SERVICES[@]}"; do
            case $SERVICE in
                "app")
                    echo "🚀 Baue und pushe Backend (app)..."
                    docker-compose build app_backend
                    docker push ghcr.io/ra1n-42/miwi/app_backend:latest
                    ;;
                "frontend")
                    echo "🚀 Baue und pushe Frontend..."
                    docker-compose build frontend
                    docker push ghcr.io/ra1n-42/miwi/frontend:latest
                    ;;
                "docker-compose.yml" | "Dockerfile")
                    echo "🚀 Änderungen an Docker-Konfiguration erkannt. Baue alle Images neu..."
                    docker-compose build
                    docker push ghcr.io/ra1n-42/miwi/app_backend:latest
                    docker push ghcr.io/ra1n-42/miwi/frontend:latest
                    break
                    ;;
            esac
        done
    fi
else
    echo "Keine alte Checksum-Datei gefunden. Starte erstmaligen Build & Push..."
    cp "$NEW_CHECKSUM_FILE" "$OLD_CHECKSUM_FILE"

    docker-compose build
    docker push ghcr.io/ra1n-42/miwi/app_backend:latest
    docker push ghcr.io/ra1n-42/miwi/frontend:latest
fi

# Aufräumen
rm "$NEW_CHECKSUM_FILE"

echo "✅ Deployment-Skript abgeschlossen!"
