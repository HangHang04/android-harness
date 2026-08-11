package dev.androidharness.companion;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;

import android.Manifest;
import android.content.ComponentName;
import android.content.Context;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

@RunWith(AndroidJUnit4.class)
public final class ManifestSecurityTest {
    @Test
    public void bridgeRequiresShellPermissionAndRequestsNoSensitiveCapabilities()
            throws PackageManager.NameNotFoundException {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext();
        PackageManager packageManager = context.getPackageManager();
        ActivityInfo receiver = packageManager.getReceiverInfo(
                new ComponentName(context, CommitTextReceiver.class),
                0);
        assertEquals(Manifest.permission.DUMP, receiver.permission);

        PackageInfo packageInfo = packageManager.getPackageInfo(
                context.getPackageName(), PackageManager.GET_PERMISSIONS);
        List<String> requested = packageInfo.requestedPermissions == null
                ? Collections.emptyList()
                : Arrays.asList(packageInfo.requestedPermissions);
        assertFalse(requested.contains(Manifest.permission.INTERNET));
        assertFalse(requested.contains(Manifest.permission.READ_EXTERNAL_STORAGE));
        assertFalse(requested.contains(Manifest.permission.WRITE_EXTERNAL_STORAGE));
    }
}
