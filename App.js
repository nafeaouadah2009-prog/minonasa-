import React, { useCallback, useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import * as Font from 'expo-font';
import * as SplashScreen from 'expo-splash-screen';
import AppNavigator from './src/navigation/AppNavigator';
import colors from './src/theme/colors';

SplashScreen.preventAutoHideAsync();

export default function App() {
  const [fontsLoaded, setFontsLoaded] = useState(false);

  const loadFonts = useCallback(async () => {
    await Font.loadAsync({
      // ملاحظة: يجب وضع ملفات الخطوط الفعلية داخل assets/fonts/
      // Tajawal: https://fonts.google.com/specimen/Tajawal (مجاني - رخصة OFL)
      // Amiri: https://fonts.google.com/specimen/Amiri (مجاني - رخصة OFL)
      'Tajawal-Regular': require('./assets/fonts/Tajawal-Regular.ttf'),
      'Tajawal-Medium': require('./assets/fonts/Tajawal-Medium.ttf'),
      'Tajawal-Bold': require('./assets/fonts/Tajawal-Bold.ttf'),
      'Amiri-Regular': require('./assets/fonts/Amiri-Regular.ttf'),
    });
    setFontsLoaded(true);
    await SplashScreen.hideAsync();
  }, []);

  React.useEffect(() => {
    loadFonts();
  }, [loadFonts]);

  if (!fontsLoaded) {
    return <View style={styles.loading} />;
  }

  return (
    <View style={styles.root}>
      <StatusBar style="light" />
      <AppNavigator />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
  },
  loading: {
    flex: 1,
    backgroundColor: colors.background,
  },
});
