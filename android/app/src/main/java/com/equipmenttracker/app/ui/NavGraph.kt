package com.equipmenttracker.app.ui

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument

object Routes {
    const val LOGIN = "login"
    const val EQUIPMENT_LIST = "equipment_list"
    const val EQUIPMENT_DETAIL = "equipment_detail/{equipmentId}"
    const val INSPECTION = "inspection/{equipmentId}"
    const val REPORT_ISSUE = "report_issue/{equipmentId}"

    fun equipmentDetail(id: Int) = "equipment_detail/$id"
    fun inspection(id: Int) = "inspection/$id"
    fun reportIssue(id: Int) = "report_issue/$id"
}

@Composable
fun AppNavGraph(navController: NavHostController = rememberNavController()) {
    NavHost(navController = navController, startDestination = Routes.LOGIN) {
        composable(Routes.LOGIN) {
            LoginScreen(
                onLoggedIn = {
                    navController.navigate(Routes.EQUIPMENT_LIST) {
                        popUpTo(Routes.LOGIN) { inclusive = true }
                    }
                },
            )
        }
        composable(Routes.EQUIPMENT_LIST) {
            EquipmentListScreen(
                onOpenEquipment = { id -> navController.navigate(Routes.equipmentDetail(id)) },
                onLoggedOut = {
                    navController.navigate(Routes.LOGIN) {
                        popUpTo(0) { inclusive = true }
                    }
                },
            )
        }
        composable(
            Routes.EQUIPMENT_DETAIL,
            arguments = listOf(navArgument("equipmentId") { type = NavType.IntType }),
        ) { backStackEntry ->
            val id = backStackEntry.arguments?.getInt("equipmentId") ?: return@composable
            EquipmentDetailScreen(
                equipmentId = id,
                onBack = { navController.popBackStack() },
                onNewInspection = { navController.navigate(Routes.inspection(id)) },
                onReportIssue = { navController.navigate(Routes.reportIssue(id)) },
            )
        }
        composable(
            Routes.INSPECTION,
            arguments = listOf(navArgument("equipmentId") { type = NavType.IntType }),
        ) { backStackEntry ->
            val id = backStackEntry.arguments?.getInt("equipmentId") ?: return@composable
            InspectionScreen(equipmentId = id, onDone = { navController.popBackStack() })
        }
        composable(
            Routes.REPORT_ISSUE,
            arguments = listOf(navArgument("equipmentId") { type = NavType.IntType }),
        ) { backStackEntry ->
            val id = backStackEntry.arguments?.getInt("equipmentId") ?: return@composable
            ReportIssueScreen(equipmentId = id, onDone = { navController.popBackStack() })
        }
    }
}
