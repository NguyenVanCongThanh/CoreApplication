package kafka

import (
	"context"
	"encoding/json"
	"fmt"
	"os"

	"example/hello/pkg/logger"

	"github.com/segmentio/kafka-go"
)

type StatusUpdateFunc func(ctx context.Context, event ProcessDocumentStatusEvent) error

func StartConsumer(ctx context.Context, onStatusUpdate StatusUpdateFunc) {
	brokers := os.Getenv("KAFKA_BROKERS")
	if brokers == "" {
		brokers = "localhost:9092"
	}

	r := kafka.NewReader(kafka.ReaderConfig{
		Brokers: []string{brokers},
		Topic:   "ai.document.processed.status",
		GroupID: "lms-service-group",
	})

	defer r.Close()
	logger.Info("Kafka Consumer started for ai.document.processed.status")

	for {
		m, err := r.ReadMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return
			}
			logger.Error("Failed to read kafka message", err)
			continue
		}

		var event ProcessDocumentStatusEvent
		if err := json.Unmarshal(m.Value, &event); err != nil {
			logger.Error("Failed to unmarshal kafka status event", err)
			continue
		}

		err = onStatusUpdate(ctx, event)
		if err != nil {
			logger.Error(fmt.Sprintf("Failed to process status update for content %d", event.ContentID), err)
		}
	}
}
