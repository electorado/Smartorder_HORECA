package com.fb.smartorder

import android.app.Application
import com.fb.smartorder.data.network.RetrofitClient
import com.fb.smartorder.util.SessionManager

class FBSmartOrderApp : Application() {
    override fun onCreate() {
        super.onCreate()
        SessionManager.init(this)
        RetrofitClient.getBaseUrl(this)
    }
}
