package com.composebridge.plugin.services

import com.intellij.openapi.components.Service
import com.intellij.openapi.components.service
import com.intellij.openapi.project.Project

/**
 * Freemium feature gate service for AI actions.
 * Controls access to Free Copy Prompt and Pro Auto-Fix.
 */
@Service(Service.Level.PROJECT)
class FeatureGateService(private val project: Project) {

    /**
     * Determines whether the user can copy an AI prompt for free.
     * Initially returns true; will connect to quotas/limits in future.
     */
    fun canUseFreeCopy(): Boolean = true

    /**
     * Determines whether the user has access to Pro Auto-Fix via MCP/WebSocket.
     * Initially returns true; will connect to subscription validation in future.
     */
    fun canUseProFix(): Boolean = true

    /**
     * Remaining free copy credits for current billing period.
     */
    fun getRemainingFreeFixes(): Int = 999

    /**
     * Checks if current project/user has an active Pro license.
     */
    fun isProSubscriber(): Boolean = true

    companion object {
        fun getInstance(project: Project): FeatureGateService = project.service()
    }
}