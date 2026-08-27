package com.spdb.powerfinance.controller;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.OffsetDateTime;
import java.util.Map;

@RestController
public class HealthController {
    private final JdbcTemplate jdbc;
    public HealthController(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @GetMapping("/api/health")
    public Map<String, Object> health() {
        Integer database = jdbc.queryForObject("SELECT 1", Integer.class);
        return Map.of("status", "UP", "database", database != null && database == 1 ? "UP" : "DOWN", "time", OffsetDateTime.now());
    }
}
