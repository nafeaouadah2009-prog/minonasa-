import React from 'react';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import colors from '../theme/colors';
import { fonts } from '../theme/typography';

import HomeScreen from '../screens/HomeScreen';
import PrayerTimesScreen from '../screens/PrayerTimesScreen';
import QuranScreen from '../screens/QuranScreen';
import SurahReaderScreen from '../screens/SurahReaderScreen';
import AdhkarScreen from '../screens/AdhkarScreen';
import AdhkarCategoryScreen from '../screens/AdhkarCategoryScreen';
import TasbihScreen from '../screens/TasbihScreen';
import SettingsScreen from '../screens/SettingsScreen';

const Tab = createBottomTabNavigator();
const HomeStack = createNativeStackNavigator();
const QuranStack = createNativeStackNavigator();
const AdhkarStack = createNativeStackNavigator();

const screenOptions = {
  headerStyle: { backgroundColor: colors.background },
  headerTintColor: colors.textPrimary,
  headerTitleStyle: { fontFamily: fonts.medium },
  headerShadowVisible: false,
};

function HomeStackScreen() {
  return (
    <HomeStack.Navigator screenOptions={screenOptions}>
      <HomeStack.Screen name="HomeMain" component={HomeScreen} options={{ headerShown: false }} />
      <HomeStack.Screen
        name="PrayerTimes"
        component={PrayerTimesScreen}
        options={{ title: 'مواقيت الصلاة' }}
      />
    </HomeStack.Navigator>
  );
}

function QuranStackScreen() {
  return (
    <QuranStack.Navigator screenOptions={screenOptions}>
      <QuranStack.Screen
        name="QuranIndex"
        component={QuranScreen}
        options={{ headerShown: false }}
      />
      <QuranStack.Screen
        name="SurahReader"
        component={SurahReaderScreen}
        options={({ route }) => ({ title: `سورة ${route.params.surahName}` })}
      />
    </QuranStack.Navigator>
  );
}

function AdhkarStackScreen() {
  return (
    <AdhkarStack.Navigator screenOptions={screenOptions}>
      <AdhkarStack.Screen
        name="AdhkarMain"
        component={AdhkarScreen}
        options={{ headerShown: false }}
      />
      <AdhkarStack.Screen
        name="AdhkarCategory"
        component={AdhkarCategoryScreen}
        options={({ route }) => ({ title: route.params.title })}
      />
    </AdhkarStack.Navigator>
  );
}

const TAB_ICONS = {
  Home: 'home-outline',
  Quran: 'book-outline',
  Adhkar: 'moon-outline',
  Tasbih: 'ellipse-outline',
  Settings: 'settings-outline',
};

const navTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.background,
    card: colors.surface,
    border: colors.border,
    primary: colors.accent,
    text: colors.textPrimary,
  },
};

export default function AppNavigator() {
  return (
    <NavigationContainer theme={navTheme}>
      <Tab.Navigator
        screenOptions={({ route }) => ({
          headerShown: false,
          tabBarStyle: {
            backgroundColor: colors.surface,
            borderTopColor: colors.border,
          },
          tabBarActiveTintColor: colors.accent,
          tabBarInactiveTintColor: colors.textMuted,
          tabBarLabelStyle: { fontFamily: fonts.body, fontSize: 11 },
          tabBarIcon: ({ color, size }) => (
            <Ionicons name={TAB_ICONS[route.name]} size={size} color={color} />
          ),
        })}
      >
        <Tab.Screen name="Home" component={HomeStackScreen} options={{ title: 'الرئيسية' }} />
        <Tab.Screen name="Quran" component={QuranStackScreen} options={{ title: 'القرآن' }} />
        <Tab.Screen name="Adhkar" component={AdhkarStackScreen} options={{ title: 'الأذكار' }} />
        <Tab.Screen name="Tasbih" component={TasbihScreen} options={{ title: 'السبحة' }} />
        <Tab.Screen name="Settings" component={SettingsScreen} options={{ title: 'الإعدادات' }} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
