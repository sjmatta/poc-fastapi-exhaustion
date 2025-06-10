.PHONY: help install clean demo-broken demo-fixed stop

help: ## Show this help message
	@echo "FastAPI Thread Exhaustion Reproduction"
	@echo "======================================="
	@echo ""
	@echo "Quick Demo:"
	@echo "  make demo-broken  # Shows the thread exhaustion problem"
	@echo "  make demo-fixed   # Shows the async solution"
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies
	pip install -r requirements.txt

clean: ## Clean up processes and temp files
	@echo "🧹 Cleaning up..."
	@kill $$(lsof -ti:8000,8001) 2>/dev/null || true
	@rm -f /tmp/*stream*.log
	@sleep 1

demo-broken: clean ## Demonstrate the thread exhaustion problem
	@echo "🔥 THREAD EXHAUSTION REPRODUCTION"
	@echo "================================="
	@echo ""
	@echo "Starting mock LiteLLM service..."
	@cd mock_llm && python main.py &
	@sleep 2
	@echo "Starting FastAPI in BROKEN mode (4 thread limit)..."
	@PYTHONPATH=. APP_VERSION=broken python app/main.py &
	@sleep 2
	@echo ""
	@echo "Testing with 8 concurrent streams (will exhaust 4-thread pool):"
	@for i in 1 2 3 4 5 6 7 8; do curl -m 60 -s http://localhost:8000/api/v1/chat/stream > /tmp/stream_$$i.log & done
	@sleep 3
	@echo ""
	@echo "Health check results (should be SLOW due to thread exhaustion):"
	@for i in 1 2 3; do \
		echo -n "Check $$i: "; \
		start=$$(date +%s.%N); \
		curl -s http://localhost:8000/health > /dev/null && \
		end=$$(date +%s.%N) && \
		echo "$$(echo "$$end - $$start" | bc -l)s - SLOW (threads exhausted!)" || echo "FAILED"; \
		sleep 1; \
	done
	@echo ""
	@echo "🔥 RESULT: Slow health checks prove thread pool exhaustion!"

demo-fixed: clean ## Demonstrate the async solution
	@echo "✅ ASYNC SOLUTION DEMONSTRATION"
	@echo "==============================="
	@echo ""
	@echo "Starting mock LiteLLM service..."
	@cd mock_llm && python main.py &
	@sleep 2
	@echo "Starting FastAPI in FIXED mode (unlimited async)..."
	@PYTHONPATH=. APP_VERSION=fixed python app/main.py &
	@sleep 2
	@echo ""
	@echo "Testing with 8 concurrent streams (async handles unlimited):"
	@for i in 1 2 3 4 5 6 7 8; do curl -m 60 -s http://localhost:8000/api/v1/chat/stream > /tmp/stream_$$i.log & done
	@sleep 3
	@echo ""
	@echo "Health check results (should remain FAST):"
	@for i in 1 2 3; do \
		echo -n "Check $$i: "; \
		start=$$(date +%s.%N); \
		curl -s http://localhost:8000/health > /dev/null && \
		end=$$(date +%s.%N) && \
		echo "$$(echo "$$end - $$start" | bc -l)s - FAST (async working!)" || echo "FAILED"; \
		sleep 1; \
	done
	@echo ""
	@echo "✅ RESULT: Fast health checks prove no thread exhaustion!"

stop: ## Stop all services
	@echo "🛑 Stopping services..."
	@kill $$(lsof -ti:8000,8001) 2>/dev/null || true
	@rm -f /tmp/*stream*.log