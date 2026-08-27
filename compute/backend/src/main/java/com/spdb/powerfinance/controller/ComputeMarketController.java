package com.spdb.powerfinance.controller;

import com.spdb.powerfinance.service.ComputeMarketService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@Validated
@RestController
@RequestMapping("/api/compute")
public class ComputeMarketController {
    private final ComputeMarketService service;

    public ComputeMarketController(ComputeMarketService service) {
        this.service = service;
    }

    @GetMapping("/summary")
    public Map<String, Object> summary() {
        return service.getSummary();
    }

    @GetMapping("/policy/overview")
    public Map<String, Object> policyOverview() {
        return service.getPolicyOverview();
    }

    @GetMapping("/opportunities")
    public Map<String, Object> opportunities() {
        return service.findFinanceOpportunities();
    }

    @GetMapping("/opportunities/{opportunityCode}")
    public Map<String, Object> opportunity(
            @PathVariable @Pattern(regexp = "[A-Za-z0-9_-]{1,40}") String opportunityCode) {
        return service.findFinanceOpportunity(opportunityCode);
    }

    @GetMapping("/facilities")
    public Map<String, Object> facilities(
            @RequestParam(defaultValue = "") String query,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return service.findFacilities(query, page, size);
    }

    @GetMapping("/facilities/{facilityCode}")
    public Map<String, Object> facility(
            @PathVariable @Pattern(regexp = "[A-Za-z0-9_-]{1,32}") String facilityCode) {
        return service.findFacility(facilityCode);
    }

    @GetMapping("/facilities/{facilityCode}/operations")
    public Map<String, Object> facilityOperations(
            @PathVariable @Pattern(regexp = "[A-Za-z0-9_-]{1,32}") String facilityCode) {
        return service.findFacilityOperations(facilityCode);
    }

    @GetMapping("/power-synergy/{facilityCode}")
    public Map<String, Object> powerSynergy(
            @PathVariable @Pattern(regexp = "[A-Za-z0-9_-]{1,32}") String facilityCode) {
        return service.findPowerSynergy(facilityCode);
    }

    @GetMapping("/products")
    public Map<String, Object> products(
            @RequestParam(defaultValue = "") String query,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return service.findProducts(query, page, size);
    }

    @GetMapping("/products/{listingId}")
    public Map<String, Object> product(@PathVariable @Min(1) long listingId) {
        return service.findProduct(listingId);
    }

    @GetMapping("/prices")
    public Map<String, Object> prices(
            @RequestParam(defaultValue = "") String query,
            @RequestParam(defaultValue = "") String priceScope,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return service.findPrices(query, priceScope, page, size);
    }

    @GetMapping("/economics")
    public Map<String, Object> economics(
            @RequestParam(defaultValue = "") String query,
            @RequestParam(defaultValue = "COMPUTE_BASE_V1") String scenarioVersion,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return service.findEconomics(query, scenarioVersion, page, size);
    }

    @GetMapping("/project-economics")
    public Map<String, Object> projectEconomics(
            @RequestParam(defaultValue = "") String query,
            @RequestParam(defaultValue = "COMPUTE_BASE_V1")
            @Pattern(regexp = "[A-Z0-9_]{1,40}") String scenarioVersion,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return service.findProjectEconomics(query, scenarioVersion, page, size);
    }

    @GetMapping("/sensitivity")
    public Map<String, Object> sensitivity(
            @RequestParam(defaultValue = "") String query,
            @RequestParam(defaultValue = "") String variableCode,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return service.findSensitivity(query, variableCode, page, size);
    }

    @GetMapping("/financing-capacity")
    public Map<String, Object> financingCapacity(
            @RequestParam(defaultValue = "") String query,
            @RequestParam(defaultValue = "COMPUTE_BASE_V1")
            @Pattern(regexp = "[A-Z0-9_]{1,40}") String scenarioVersion,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return service.findFinancingCapacity(query, scenarioVersion, page, size);
    }

    @GetMapping("/financing-capacity/{projectEconomicsResultId}/curve")
    public Map<String, Object> financingCurve(
            @PathVariable @Min(1) long projectEconomicsResultId) {
        return service.findFinancingCurve(projectEconomicsResultId);
    }

    @GetMapping("/credit-policies")
    public Map<String, Object> creditPolicies() {
        return service.findCreditPolicies();
    }

    @GetMapping("/bank-recommendations")
    public Map<String, Object> bankRecommendations(
            @RequestParam(defaultValue = "") String query,
            @RequestParam(defaultValue = "COMPUTE_BASE_V1")
            @Pattern(regexp = "[A-Z0-9_]{1,40}") String scenarioVersion,
            @RequestParam(defaultValue = "CREDIT_BASE_V1")
            @Pattern(regexp = "[A-Z0-9_]{1,40}") String policyCode,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size) {
        return service.findBankRecommendations(query, scenarioVersion, policyCode, page, size);
    }

    @GetMapping("/bank-recommendations/{projectEconomicsResultId}/curve")
    public Map<String, Object> bankRecommendationCurve(
            @PathVariable @Min(1) long projectEconomicsResultId,
            @RequestParam(defaultValue = "CREDIT_BASE_V1")
            @Pattern(regexp = "[A-Z0-9_]{1,40}") String policyCode) {
        return service.findCreditPolicyCurve(projectEconomicsResultId, policyCode);
    }
}
