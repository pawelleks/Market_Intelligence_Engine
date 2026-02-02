FROM eclipse-temurin:17-jre

WORKDIR /app

# Copy downloaded JAR and config
COPY ThetaTerminal.jar .
COPY config.properties .

# Expose the default port
EXPOSE 25510

# Launch with positional arguments and config
CMD java -jar ThetaTerminal.jar --config config.properties "${THETADATA_USERNAME}" "${THETADATA_PASSWORD}"
