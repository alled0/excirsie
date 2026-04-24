FROM eclipse-temurin:17-jre-jammy

WORKDIR /app

COPY target/workout-api-1.0.0.jar app.jar

RUN mkdir -p data

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
