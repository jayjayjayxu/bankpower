package com.spdb.powerfinance.controller;

import com.spdb.powerfinance.service.SynergySimulationService;
import jakarta.validation.constraints.Pattern;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

@RestController
@Validated
@RequestMapping("/api/compute/simulation")
public class SynergySimulationController {
    private final SynergySimulationService service;
    public SynergySimulationController(SynergySimulationService service) { this.service=service; }
    @GetMapping("/{facilityCode}")
    public Map<String,Object> overview(@PathVariable @Pattern(regexp="[A-Za-z0-9_-]{1,32}") String facilityCode) {
        return service.overview(facilityCode);
    }
}
