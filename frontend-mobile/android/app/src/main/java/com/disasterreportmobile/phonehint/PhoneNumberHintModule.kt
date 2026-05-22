package com.disasterreportmobile.phonehint

import android.app.Activity
import android.content.Intent
import android.content.IntentSender
import com.facebook.react.bridge.ActivityEventListener
import com.facebook.react.bridge.Arguments
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod
import com.facebook.react.bridge.WritableMap
import com.google.android.gms.auth.api.identity.GetPhoneNumberHintIntentRequest
import com.google.android.gms.auth.api.identity.Identity
import com.google.android.gms.common.api.ApiException

class PhoneNumberHintModule(reactContext: ReactApplicationContext) :
    ReactContextBaseJavaModule(reactContext), ActivityEventListener {

    init {
        reactContext.addActivityEventListener(this)
    }

    override fun getName(): String = NAME

    private var pendingPromise: Promise? = null

    @ReactMethod
    fun requestPhoneNumber(promise: Promise) {
        val activity = reactApplicationContext.currentActivity
        if (activity == null) {
            promise.reject(ERR_NO_ACTIVITY, "目前無 Activity，無法呼叫 Phone Number Hint")
            return
        }
        if (pendingPromise != null) {
            promise.reject(ERR_IN_PROGRESS, "已有 Phone Number Hint 請求進行中")
            return
        }
        pendingPromise = promise

        val request = GetPhoneNumberHintIntentRequest.builder().build()
        Identity.getSignInClient(activity)
            .getPhoneNumberHintIntent(request)
            .addOnSuccessListener { result ->
                try {
                    activity.startIntentSenderForResult(
                        result.intentSender,
                        REQUEST_CODE,
                        null, 0, 0, 0,
                    )
                } catch (e: IntentSender.SendIntentException) {
                    rejectPending(ERR_LAUNCH, e.message ?: "啟動電話選單失敗")
                }
            }
            .addOnFailureListener { error ->
                // 多數失敗情境（無 SIM、無 Google Play Services）回傳「取消」較合理，
                // App 端可 fallback 為手動輸入。
                resolveCanceled(reason = error.message)
            }
    }

    override fun onActivityResult(
        activity: Activity,
        requestCode: Int,
        resultCode: Int,
        data: Intent?,
    ) {
        if (requestCode != REQUEST_CODE) return
        if (resultCode != Activity.RESULT_OK || data == null) {
            resolveCanceled(reason = "user_canceled")
            return
        }
        try {
            val phone = Identity.getSignInClient(activity).getPhoneNumberFromIntent(data)
            val map: WritableMap = Arguments.createMap().apply {
                putString("phoneNumber", phone)
                putBoolean("canceled", false)
            }
            pendingPromise?.resolve(map)
            pendingPromise = null
        } catch (e: ApiException) {
            rejectPending(ERR_PARSE, e.message ?: "解析電話號碼失敗")
        }
    }

    override fun onNewIntent(intent: Intent) {
        // No-op: Phone Hint flow uses startIntentSenderForResult.
    }

    private fun resolveCanceled(reason: String? = null) {
        val map = Arguments.createMap().apply {
            putBoolean("canceled", true)
            if (reason != null) putString("reason", reason)
        }
        pendingPromise?.resolve(map)
        pendingPromise = null
    }

    private fun rejectPending(code: String, message: String) {
        pendingPromise?.reject(code, message)
        pendingPromise = null
    }

    companion object {
        const val NAME = "PhoneNumberHint"
        private const val REQUEST_CODE = 9087
        private const val ERR_NO_ACTIVITY = "E_NO_ACTIVITY"
        private const val ERR_IN_PROGRESS = "E_IN_PROGRESS"
        private const val ERR_LAUNCH = "E_LAUNCH"
        private const val ERR_PARSE = "E_PARSE"
    }
}
