package com.composebridge.agent

import android.content.Context
import android.net.Uri
import androidx.core.content.FileProvider
import java.io.File

/**
 * Custom FileProvider subclass for ComposeBridge to avoid Android manifest merger
 * collisions with host applications having their own FileProvider declaration.
 */
class ComposeBridgeFileProvider : FileProvider() {
    companion object {
        fun getUriForFile(context: Context, authority: String, file: File): Uri {
            return FileProvider.getUriForFile(context, authority, file)
        }
    }
}
