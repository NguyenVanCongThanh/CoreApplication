package com.example.demo.controller;

import com.example.demo.service.admin.AdminLlmService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * RBAC-gated proxy for the AI service's internal LLM registry admin API.
 *
 * All routes require {@code ROLE_ADMIN}; the service layer injects the
 * shared {@code X-AI-Secret} header so the frontend never sees it.
 *
 * Request/response bodies are forwarded as Map / List of Maps so this
 * controller doesn't drift from the FastAPI schema. See
 * {@code ai-service/app/api/endpoints/admin_llm.py} for the authoritative
 * shapes.
 */
@RestController
@RequestMapping("/api/admin/llm")
@RequiredArgsConstructor
@PreAuthorize("hasRole('ADMIN')")
public class AdminLlmController {

    private final AdminLlmService adminLlmService;

    // ── Catalogue ──────────────────────────────────────────────────────────
    @GetMapping("/catalogue")
    public ResponseEntity<Map<String, Object>> catalogue() {
        return ResponseEntity.ok(adminLlmService.getCatalogue());
    }

    // ── Providers ──────────────────────────────────────────────────────────
    @GetMapping("/providers")
    public ResponseEntity<List<Map<String, Object>>> listProviders() {
        return ResponseEntity.ok(adminLlmService.listProviders());
    }

    @PostMapping("/providers")
    public ResponseEntity<Map<String, Object>> upsertProvider(
            @RequestBody Map<String, Object> body) {
        return ResponseEntity.ok(adminLlmService.upsertProvider(body));
    }

    @PatchMapping("/providers/{id}")
    public ResponseEntity<Map<String, Object>> updateProvider(
            @PathVariable long id, @RequestBody Map<String, Object> body) {
        return ResponseEntity.ok(adminLlmService.updateProvider(id, body));
    }

    @DeleteMapping("/providers/{id}")
    public ResponseEntity<Void> deleteProvider(@PathVariable long id) {
        adminLlmService.deleteProvider(id);
        return ResponseEntity.noContent().build();
    }

    // ── Models ─────────────────────────────────────────────────────────────
    @GetMapping("/models")
    public ResponseEntity<List<Map<String, Object>>> listModels(
            @RequestParam(required = false) Long providerId,
            @RequestParam(required = false) Boolean onlyEnabled) {
        return ResponseEntity.ok(adminLlmService.listModels(providerId, onlyEnabled));
    }

    @PostMapping("/models")
    public ResponseEntity<Map<String, Object>> upsertModel(@RequestBody Map<String, Object> body) {
        return ResponseEntity.ok(adminLlmService.upsertModel(body));
    }

    @PatchMapping("/models/{id}")
    public ResponseEntity<Map<String, Object>> updateModel(
            @PathVariable long id, @RequestBody Map<String, Object> body) {
        return ResponseEntity.ok(adminLlmService.updateModel(id, body));
    }

    @DeleteMapping("/models/{id}")
    public ResponseEntity<Void> deleteModel(@PathVariable long id) {
        adminLlmService.deleteModel(id);
        return ResponseEntity.noContent().build();
    }

    // ── API keys ───────────────────────────────────────────────────────────
    @GetMapping("/keys")
    public ResponseEntity<List<Map<String, Object>>> listKeys(
            @RequestParam(required = false) Long providerId) {
        return ResponseEntity.ok(adminLlmService.listApiKeys(providerId));
    }

    @PostMapping("/keys")
    public ResponseEntity<Map<String, Object>> createKey(@RequestBody Map<String, Object> body) {
        return ResponseEntity.ok(adminLlmService.createApiKey(body));
    }

    @PatchMapping("/keys/{id}")
    public ResponseEntity<Map<String, Object>> updateKey(
            @PathVariable long id, @RequestBody Map<String, Object> body) {
        return ResponseEntity.ok(adminLlmService.updateApiKey(id, body));
    }

    @DeleteMapping("/keys/{id}")
    public ResponseEntity<Void> deleteKey(@PathVariable long id) {
        adminLlmService.deleteApiKey(id);
        return ResponseEntity.noContent().build();
    }

    // ── Task bindings ──────────────────────────────────────────────────────
    @GetMapping("/bindings")
    public ResponseEntity<List<Map<String, Object>>> listBindings(
            @RequestParam(required = false) String taskCode) {
        return ResponseEntity.ok(adminLlmService.listBindings(taskCode));
    }

    @PostMapping("/bindings")
    public ResponseEntity<Map<String, Object>> upsertBinding(@RequestBody Map<String, Object> body) {
        return ResponseEntity.ok(adminLlmService.upsertBinding(body));
    }

    @PatchMapping("/bindings/{id}")
    public ResponseEntity<Map<String, Object>> updateBinding(
            @PathVariable long id, @RequestBody Map<String, Object> body) {
        return ResponseEntity.ok(adminLlmService.updateBinding(id, body));
    }

    @DeleteMapping("/bindings/{id}")
    public ResponseEntity<Void> deleteBinding(@PathVariable long id) {
        adminLlmService.deleteBinding(id);
        return ResponseEntity.noContent().build();
    }

    // ── Usage + sanity test ────────────────────────────────────────────────
    @GetMapping("/usage")
    public ResponseEntity<Map<String, Object>> usage(
            @RequestParam(defaultValue = "24") int sinceHours,
            @RequestParam(required = false) String taskCode) {
        return ResponseEntity.ok(adminLlmService.usage(sinceHours, taskCode));
    }

    @PostMapping("/test-call")
    public ResponseEntity<Map<String, Object>> testCall(@RequestBody Map<String, Object> body) {
        return ResponseEntity.ok(adminLlmService.testCall(body));
    }
}