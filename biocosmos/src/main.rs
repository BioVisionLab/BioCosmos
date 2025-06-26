use actix_web::{App, HttpResponse, HttpServer, Responder, web};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    HttpServer::new(|| {
        App::new()
            .route("/", web::get().to(greet))
            .route("/health", web::get().to(health_check))
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await?;

    Ok(())
}

async fn greet() -> &'static str {
    "Hello, BioCosmos!"
}

async fn health_check() -> HttpResponse {
    HttpResponse::Ok().body("Service is healthy")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_greet() {
        let response = greet().await;
        assert_eq!(response, "Hello, BioCosmos!");
    }

    #[tokio::test]
    async fn test_health_check() {
        let response = health_check().await;
        use actix_web::body::{MessageBody, to_bytes};
        let body_bytes = to_bytes(response.into_body()).await.unwrap();
        let body_str = std::str::from_utf8(&body_bytes).unwrap();
        assert_eq!(body_str, "Service is healthy");
        assert!(response.status().is_success());
    }
}
