package com.spdb.powerfinance.controller;

import com.spdb.powerfinance.service.BankWorkbenchService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/bank-workbench")
public class BankWorkbenchController {
    private final BankWorkbenchService service;

    public BankWorkbenchController(BankWorkbenchService service) {
        this.service = service;
    }

    @GetMapping
    public Map<String, Object> overview() {
        return service.getOverview();
    }
}
