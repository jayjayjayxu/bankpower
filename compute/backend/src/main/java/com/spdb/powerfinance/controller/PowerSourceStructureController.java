package com.spdb.powerfinance.controller;

import com.spdb.powerfinance.service.PowerSourceStructureService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/power-source-structure")
public class PowerSourceStructureController {
    private final PowerSourceStructureService service;

    public PowerSourceStructureController(PowerSourceStructureService service) {
        this.service = service;
    }

    @GetMapping("/overview")
    public Map<String, Object> overview() {
        return service.getOverview();
    }
}
