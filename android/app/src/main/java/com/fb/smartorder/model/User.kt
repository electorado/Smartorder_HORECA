package com.fb.smartorder.model

import com.google.gson.annotations.SerializedName

data class UserRegisterRequest(
    @SerializedName("name")
    val name: String,

    @SerializedName("email")
    val email: String,

    @SerializedName("password")
    val password: String,

    @SerializedName("restaurant_name")
    val restaurantName: String
)

data class UserLoginRequest(
    @SerializedName("email")
    val email: String,

    @SerializedName("password")
    val password: String
)

data class UserData(
    @SerializedName("id")
    val id: String?,

    @SerializedName("name")
    val name: String,

    @SerializedName("email")
    val email: String,

    @SerializedName("restaurant_name")
    val restaurantName: String
)

data class AuthResponse(
    @SerializedName("message")
    val message: String,

    @SerializedName("user")
    val user: UserData?
)

data class UserUpdateRequest(
    @SerializedName("name")
    val name: String?,

    @SerializedName("restaurant_name")
    val restaurantName: String?,

    @SerializedName("password")
    val password: String? = null
)

data class ForgotPasswordRequest(
    @SerializedName("email")
    val email: String,

    @SerializedName("new_password")
    val newPassword: String? = null
)
