package com.spdb.powerfinance.controller;

import com.spdb.powerfinance.service.EnterpriseQueryService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@Validated
@RestController
@RequestMapping("/api/enterprises")
public class EnterpriseController {
    private final EnterpriseQueryService service;

    public EnterpriseController(EnterpriseQueryService service) { this.service = service; }

    @GetMapping("/home-summary")
    public Map<String, Object> homeSummary() { return service.getHomeSummary(); }

    @GetMapping
    public List<Map<String, Object>> findEnterprises(
            @RequestParam(defaultValue = "") String query,
            @RequestParam(defaultValue = "100") @Min(1) @Max(200) int limit) {
        return service.findEnterprises(query, limit);
    }

    @GetMapping("/{companyId}")
    public Map<String, Object> findEnterprise(
            @PathVariable @Pattern(regexp = "[A-Za-z0-9_-]{1,16}") String companyId) {
        return service.findEnterpriseDetail(companyId);
    }

    @GetMapping("/{companyId}/hourly-load")
    public Map<String, Object> findHourlyLoad(
            @PathVariable @Pattern(regexp = "[A-Za-z0-9_-]{1,16}") String companyId,
            @RequestParam(required = false) @Min(2000) @Max(2100) Integer year,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "24") @Min(1) @Max(744) int size) {
        return service.findHourlyLoad(companyId, year, page, size);
    }

    @GetMapping("/{companyId}/load-price-window")
    public Map<String, Object> findLoadPriceWindow(
            @PathVariable @Pattern(regexp = "[A-Za-z0-9_-]{1,16}") String companyId,
            @RequestParam(defaultValue = "2025") @Min(2000) @Max(2100) int year) {
        return service.findLoadPriceWindow(companyId, year);
    }

    @GetMapping("/{companyId}/hourly-generation")
    public Map<String, Object> findHourlyGeneration(
            @PathVariable @Pattern(regexp = "[A-Za-z0-9_-]{1,16}") String companyId,
            @RequestParam(required = false) @Min(2000) @Max(2100) Integer year,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "24") @Min(1) @Max(744) int size) {
        return service.findHourlyGeneration(companyId, year, page, size);
    }
}
